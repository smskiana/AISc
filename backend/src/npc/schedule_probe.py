"""编辑器专用日程 planner 白名单隔离探针。"""
from __future__ import annotations

import asyncio
import re

from ..application.operation_context import BrainOperationContext, GameTimeSnapshot
from .daily_schedule import DailyScheduleBatchRequest, DailySchedulePlanner, NpcScheduleRequest


class _ProbeCatalog:
    """提供不写共享配置的固定候选目录。"""

    action_ids = {"eat", "read", "rest", "visit", "work_open", "walk"}

    def allowed_locations(self, npc_id: str, action_id: str) -> list[str]:
        """为每个探针 action 返回唯一稳定地点。"""
        return [f"probe.{action_id}"]

    def task_runtime_metadata(self, action_id: str) -> dict:
        """为探针候选声明稳定运行时语义。"""
        return {"segment_id": "work" if action_id in {"read", "walk"} else "rest",
                "completion_policy_id": "duration", "interrupt_policy": "fully_interruptible",
                "duration_gameplay_seconds": 60, "lifecycle_action": action_id == "work_open"}


async def run_daily_schedule_probe(scenario: str) -> dict:
    """调用正式 DailySchedulePlanner seam，且只写函数内存。"""
    scenario = (scenario or "").strip().lower()
    routines = tuple((8 + index, 0, action, f"probe.{action}") for index, action in enumerate(sorted(_ProbeCatalog.action_ids)))
    context = BrainOperationContext("diagnostic_schedule_probe", GameTimeSnapshot(1, 8, 0, "sunny", 1), 1)
    request = DailyScheduleBatchRequest(context, (NpcScheduleRequest("diagnostic_probe", {}, routines, {}),))

    if scenario == "fixed_input_planner":
        async def provider(_messages: list[dict]) -> str:
            candidates = re.findall(r'<candidate id="([^"]+)" segment="([^"]+)"', _messages[0]["content"])
            work = [candidate_id for candidate_id, segment in candidates if segment == "work"]
            rest = [candidate_id for candidate_id, segment in candidates if segment == "rest"]
            return '{"work_tasks":' + str(work).replace("'", '"') + ',"rest_tasks":' + str(rest).replace("'", '"') + '}'
        planner = DailySchedulePlanner(_ProbeCatalog(), provider, timeout_seconds=1.0)
    elif scenario == "provider_timeout":
        async def provider(_messages: list[dict]) -> str:
            await asyncio.sleep(0.05)
            return "[]"
        planner = DailySchedulePlanner(_ProbeCatalog(), provider, timeout_seconds=0.001)
    else:
        return {"success": False, "scenario": scenario, "write_scope": "isolated_in_memory_only", "failure_reason": "unknown_backend_schedule_probe_scenario"}

    result = (await planner.prepare_day(request)).results[0]
    trace = planner.diagnostics.snapshot(npc_id="diagnostic_probe")[0]
    return {
        "success": result.status == "success" if scenario == "fixed_input_planner" else result.failure_reason == "provider_timeout",
        "scenario": scenario,
        "write_scope": "isolated_in_memory_only",
        "status": result.status,
        "failure_reason": result.failure_reason,
        "item_count": len(result.work_tasks) + len(result.rest_tasks),
        "operation_id": result.operation_id,
        "trace": trace,
    }
