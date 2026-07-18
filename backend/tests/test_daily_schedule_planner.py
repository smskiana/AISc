"""DailySchedulePlanner 公开 seam 与硬约束测试。"""
from __future__ import annotations

import asyncio
import unittest

from backend.src.application.operation_context import BrainOperationContext, GameTimeSnapshot
from backend.src.npc.daily_schedule import DailyScheduleBatchRequest, DailySchedulePlanner, NpcScheduleRequest
from backend.src.npc.schedule_candidates import ScheduleCandidate, deterministic_fallback


class _Catalog:
    """提供测试所需的最小 affordance 目录。"""

    action_ids = {"eat", "read", "work_open", "visit"}

    def allowed_locations(self, npc_id, action_id):
        return [f"zone.{action_id}"]


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
            return '[{"candidate_id":"made_up","planned_start_time":"08:00"}]'

        planner = DailySchedulePlanner(_Catalog(), invalid)
        first = (await planner.prepare_day(self._request())).results[0]
        second = (await planner.prepare_day(self._request())).results[0]
        self.assertEqual("fallback", first.status)
        self.assertEqual([(x.action_id, x.planned_start_time) for x in first.items], [(x.action_id, x.planned_start_time) for x in second.items])

    async def test_timeout_does_not_wait_for_provider(self):
        """单 owner 超时应快速收口并输出 fallback。"""
        async def slow(_messages):
            await asyncio.sleep(0.2)
            return "[]"

        planner = DailySchedulePlanner(_Catalog(), slow, timeout_seconds=0.01)
        result = (await planner.prepare_day(self._request())).results[0]
        self.assertEqual("provider_timeout", result.failure_reason)
        self.assertGreater(len(result.items), 0)

    def test_required_precedes_optional(self):
        """高相关度 optional 不能淘汰 required。"""
        candidates = [
            ScheduleCandidate("optional", "read", "z.r", "optional", "exploration", ("exploration",), 99, "08:00"),
            ScheduleCandidate("required", "eat", "z.e", "required", "need", ("need",), 0, "09:00"),
        ]
        selected, _, _ = deterministic_fallback(candidates, 1, "sakura", target_count=1)
        self.assertEqual("required", selected[0].candidate_id)

    def test_game_time_rejects_out_of_range_values(self):
        """冻结时间不接受 day 0 或越界时分。"""
        with self.assertRaisesRegex(ValueError, "invalid_game_time_snapshot"):
            GameTimeSnapshot.from_dict({"day": 0, "hour": 24, "minute": 60})


if __name__ == "__main__":
    unittest.main()
