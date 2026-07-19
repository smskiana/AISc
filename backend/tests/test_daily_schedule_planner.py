"""DailySchedulePlanner 公开 seam 与硬约束测试。"""
from __future__ import annotations

import asyncio
import hashlib
import json
import unittest

from backend.src.application.operation_context import BrainOperationContext, GameTimeSnapshot
from backend.src.npc.daily_schedule import DailyScheduleBatchRequest, DailySchedulePlanner, InteractionReplanRequest, NpcScheduleRequest
from backend.src.npc.schedule_candidates import ScheduleCandidate, deterministic_fallback
from backend.src.npc.schedule_prompt_adapter import parse_selection
from backend.src.npc.schedule_validation import validate_selection
from backend.src.npc.schedule_probe import run_daily_schedule_probe


class _Catalog:
    """提供测试所需的最小 affordance 目录。"""

    action_ids = {"eat", "read", "work_open", "visit"}

    def allowed_locations(self, npc_id, action_id):
        return [f"zone.{action_id}"]

    def task_runtime_metadata(self, action_id):
        """声明测试候选的双段运行时语义。"""
        return {"segment_id": "work" if action_id in {"read"} else "rest",
                "completion_policy_id": "duration", "interrupt_policy": "fully_interruptible",
                "duration_gameplay_seconds": 60, "lifecycle_action": action_id == "work_open"}


class DailySchedulePlannerTests(unittest.IsolatedAsyncioTestCase):
    """验证 planner 的确定性、严格校验和 owner 超时隔离。"""

    def _request(self):
        """建立单 owner 的冻结请求。"""
        context = BrainOperationContext("op", GameTimeSnapshot(3, 8, 0, "rainy", 7), 11)
        owner = NpcScheduleRequest("sakura", {}, ((8, 0, "work_open", "zone.work_open"),), {})
        return DailyScheduleBatchRequest(context, (owner,))

    async def test_unknown_candidate_falls_back_with_stable_seed(self):
        """未知 candidate 不得部分接受，重复运行产生相同 fallback。"""
        async def invalid(_messages):
            return '{"work_tasks":["made_up"],"rest_tasks":[]}'

        planner = DailySchedulePlanner(_Catalog(), invalid)
        first = (await planner.prepare_day(self._request())).results[0]
        second = (await planner.prepare_day(self._request())).results[0]
        self.assertEqual("fallback", first.status)
        self.assertEqual(first.work_tasks + first.rest_tasks, second.work_tasks + second.rest_tasks)
        self.assertEqual("unknown_candidate", planner.diagnostics.snapshot(npc_id="sakura")[-1]["failure_detail"])

    async def test_timeout_does_not_wait_for_provider(self):
        """单 owner 超时应快速收口并输出 fallback。"""
        async def slow(_messages):
            await asyncio.sleep(0.2)
            return "[]"

        planner = DailySchedulePlanner(_Catalog(), slow, timeout_seconds=0.01)
        result = (await planner.prepare_day(self._request())).results[0]
        self.assertEqual("provider_timeout", result.failure_reason)
        self.assertGreater(len(result.work_tasks) + len(result.rest_tasks), 0)
        trace = planner.diagnostics.snapshot(npc_id="sakura")[0]
        self.assertEqual("completed", trace["execution_phase"])
        self.assertEqual("provider_timeout", trace["validation_status"])
        self.assertEqual(str(int(trace["fallback_seed"])), trace["fallback_seed"])
        self.assertTrue(trace["candidate_group_counts"])
        self.assertLessEqual(len(trace["fallback_reasons"]), 50)

    def test_required_precedes_optional(self):
        """高相关度 optional 不能淘汰 required。"""
        candidates = [
            ScheduleCandidate("optional", "read", "z.r", "optional", "exploration", ("exploration",), 99, "08:00"),
            ScheduleCandidate("required", "eat", "z.e", "required", "need", ("need",), 0, "09:00"),
        ]
        selected, _, _ = deterministic_fallback(candidates, 1, "sakura", target_count=1)
        self.assertEqual("required", selected[0].candidate_id)

    def test_parse_normalizes_order_and_exact_duplicates(self):
        """模型乱序和完全重复项可确定性收口，非 object 必须稳定拒绝。"""
        candidates = {str(i): object() for i in range(6)}
        raw = '{"work_tasks":["0","1","2"],"rest_tasks":["3","4","5"]}'
        selected = parse_selection(raw, candidates)
        self.assertEqual(["0", "1", "2"], selected["work"])
        with self.assertRaisesRegex(ValueError, "segment_queue_not_array"):
            parse_selection('{"work_tasks":null,"rest_tasks":[]}', candidates)

    def test_required_group_accepts_one_alternative(self):
        """同一 required group 的多个地点只要求命中一个候选。"""
        candidates = [
            ScheduleCandidate("eat_a", "eat", "a", "required", "need", ("need",), 1, "08:00", required_group_id="need:eat", segment_id="rest"),
            ScheduleCandidate("eat_b", "eat", "b", "required", "need", ("need",), 1, "09:00", required_group_id="need:eat", segment_id="rest"),
        ] + [ScheduleCandidate(f"o{i}", "read", f"r{i}", "optional", "exploration", ("exploration",), 1, f"{10+i:02d}:00", segment_id="work") for i in range(5)]
        validate_selection({"work": [f"o{i}" for i in range(5)], "rest": ["eat_a"]}, candidates)

    def test_game_time_rejects_out_of_range_values(self):
        """冻结时间不接受 day 0 或越界时分。"""
        with self.assertRaisesRegex(ValueError, "invalid_game_time_snapshot"):
            GameTimeSnapshot.from_dict({"day": 0, "hour": 24, "minute": 60})

    async def test_runtime_recovery_has_distinct_eligibility(self):
        """执行失败恢复不要求伪造 completed interaction，但必须使用日程触发类型。"""
        async def valid(_messages):
            return '{"work_tasks":[],"rest_tasks":[]}'

        batch = self._request()
        base = InteractionReplanRequest(batch.context, batch.owners[0], "schedule_failed", ("sakura",), "runtime_recovery", "movement_not_completed", ())
        accepted = await DailySchedulePlanner(_Catalog(), valid).replan_after_runtime_recovery(base)
        rejected = await DailySchedulePlanner(_Catalog(), valid).replan_after_runtime_recovery(
            InteractionReplanRequest(batch.context, batch.owners[0], "player_dialogue", ("sakura",), "runtime_recovery", "", ())
        )
        self.assertNotEqual("runtime_recovery_type_invalid", accepted.failure_reason)
        self.assertEqual("runtime_recovery_type_invalid", rejected.failure_reason)

    async def test_plan_contains_no_precise_task_times(self):
        """双段任务不得携带普通任务精确时间点。"""
        async def expired(_messages):
            actions = ("work_open", "eat", "read", "visit")
            ids = [hashlib.sha256(f"sakura|{action}|zone.{action}".encode()).hexdigest()[:16] for action in actions]
            return json.dumps({"work_tasks": ids[1:2], "rest_tasks": ids[2:]})

        batch = self._request()
        context = BrainOperationContext("replan", GameTimeSnapshot(3, 8, 30, "rainy", 8), 12)
        request = InteractionReplanRequest(context, batch.owners[0], "schedule_window_expired", ("sakura",), "runtime_recovery", "window_expired", ())
        result = await DailySchedulePlanner(_Catalog(), expired).replan_after_runtime_recovery(request)

        self.assertTrue(result.work_tasks or result.rest_tasks)
        self.assertTrue(all(not hasattr(item, "planned_start_time") for item in result.work_tasks + result.rest_tasks))

    async def test_editor_schedule_probes_use_isolated_official_seam(self):
        """固定输入与 timeout 探针均应隔离写入并返回完整 trace。"""
        fixed = await run_daily_schedule_probe("fixed_input_planner")
        timeout = await run_daily_schedule_probe("provider_timeout")
        self.assertTrue(fixed["success"])
        self.assertEqual("success", fixed["status"])
        self.assertEqual(5, fixed["item_count"])
        self.assertTrue(timeout["success"])
        self.assertEqual("provider_timeout", timeout["failure_reason"])
        self.assertEqual("isolated_in_memory_only", timeout["write_scope"])


if __name__ == "__main__":
    unittest.main()
