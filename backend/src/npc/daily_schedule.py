"""NPC 日程深模块的公开契约与编排。"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable

from ..application.operation_context import BrainOperationContext
from .schedule_candidates import ScheduleCandidate, ScheduleCandidateBuilder, deterministic_fallback
from .schedule_diagnostics import ScheduleDiagnostics, ScheduleOwnerTrace
from .schedule_prompt_adapter import parse_selection, render_candidates


@dataclass(frozen=True)
class DailyScheduleItem:
    """跨端持久化的单个日程项。"""

    candidate_id: str
    action_id: str
    location_id: str
    planned_start_time: str
    necessity: str
    primary_group: str
    groups: tuple[str, ...]
    evidence_ids: tuple[str, ...] = ()
    target_person_id: str = ""
    execution_window_before_minutes: int = 30
    execution_window_after_minutes: int = 30
    source: str = "fallback"
    miss_policy: str = "skip_next"


@dataclass(frozen=True)
class NpcScheduleRequest:
    """提供单名 NPC 规划所需的冻结输入。"""

    npc_id: str
    profile: dict
    routines: tuple[tuple[int, int, str, str], ...]
    physical_state: dict
    plan_context: str = ""
    base_schedule_revision: int = 0


@dataclass(frozen=True)
class DailyScheduleBatchRequest:
    """绑定同一世界快照的一批 NPC 日程请求。"""

    context: BrainOperationContext
    owners: tuple[NpcScheduleRequest, ...]


@dataclass(frozen=True)
class NpcScheduleResult:
    """返回可由 Unity 整体接收的已验证计划。"""

    operation_id: str
    npc_id: str
    game_day: int
    schedule_revision: int
    planner_version: str
    items: tuple[DailyScheduleItem, ...]
    status: str
    failure_reason: str = ""


@dataclass(frozen=True)
class DailyScheduleBatchResult:
    """汇总并发 owner 结果，不因单个失败丢弃其他计划。"""

    operation_id: str
    results: tuple[NpcScheduleResult, ...]


@dataclass(frozen=True)
class InteractionReplanRequest:
    """基于 Unity 权威剩余计划发起一次互动后重规划。"""

    context: BrainOperationContext
    owner: NpcScheduleRequest
    interaction_type: str
    participant_ids: tuple[str, ...]
    end_reason: str
    interaction_summary: str
    remaining_schedule: tuple[DailyScheduleItem, ...]


class DailySchedulePlanner:
    """统一执行候选构建、LLM 选择、校验、超时与 fallback。"""

    PLANNER_VERSION = "daily_schedule_v1"

    def __init__(self, catalog, llm_call: Callable[[list[dict]], Awaitable[str]], timeout_seconds: float = 120.0, diagnostics: ScheduleDiagnostics | None = None):
        self._builder = ScheduleCandidateBuilder(catalog)
        self._llm_call = llm_call
        self._timeout_seconds = timeout_seconds
        self.diagnostics = diagnostics or ScheduleDiagnostics()

    async def prepare_day(self, request: DailyScheduleBatchRequest) -> DailyScheduleBatchResult:
        """并发规划所有 owner，并为每个 owner 独立收口。"""
        results = await asyncio.gather(*(self._prepare_owner(request.context, owner) for owner in request.owners))
        return DailyScheduleBatchResult(request.context.operation_id, tuple(results))

    async def replan_after_interaction(self, request: InteractionReplanRequest) -> NpcScheduleResult:
        """仅对有效互动基于 base revision 生成完整替换结果。"""
        if request.end_reason != "completed" or not request.interaction_summary.strip():
            return NpcScheduleResult(request.context.operation_id, request.owner.npc_id, request.context.game_time.day, request.owner.base_schedule_revision, self.PLANNER_VERSION, request.remaining_schedule, "skipped", "interaction_not_eligible")
        return await self._prepare_owner(request.context, request.owner)

    async def _prepare_owner(self, context: BrainOperationContext, owner: NpcScheduleRequest) -> NpcScheduleResult:
        """执行单 owner operation，超时后隔离迟到供应商结果。"""
        operation_id = f"{context.operation_id}:{owner.npc_id}:{uuid.uuid4().hex[:8]}"
        started = time.perf_counter()
        candidates = self._builder.build(owner.npc_id, list(owner.routines), owner.physical_state)
        trace = ScheduleOwnerTrace(operation_id, owner.npc_id, context.game_time.day, candidate_count=len(candidates))
        self.diagnostics.publish(trace)
        try:
            messages = [{"role": "user", "content": self._prompt(context, owner, candidates)}]
            raw = await asyncio.wait_for(self._llm_call(messages), timeout=self._timeout_seconds)
            by_id = {item.candidate_id: item for item in candidates}
            selected = parse_selection(raw, by_id)
            items = tuple(self._to_item(by_id[candidate_id], start, "llm") for candidate_id, start in selected)
            if not items:
                raise ValueError("empty_schedule")
            trace.status = "success"
        except asyncio.TimeoutError:
            items, seed = self._fallback(candidates, context.game_time.day, owner.npc_id)
            trace.status, trace.failure_reason, trace.fallback_seed = "fallback", "provider_timeout", seed
            trace.provider_call_not_cancelled = True
        except Exception as error:
            items, seed = self._fallback(candidates, context.game_time.day, owner.npc_id)
            trace.status, trace.failure_reason, trace.fallback_seed = "fallback", f"planner_rejected:{type(error).__name__}", seed
        trace.selected_count = len(items)
        trace.elapsed_sec = time.perf_counter() - started
        self.diagnostics.publish(trace)
        return NpcScheduleResult(operation_id, owner.npc_id, context.game_time.day, owner.base_schedule_revision + 1, self.PLANNER_VERSION, items, trace.status, trace.failure_reason)

    def _fallback(self, candidates: list[ScheduleCandidate], day: int, npc_id: str) -> tuple[tuple[DailyScheduleItem, ...], int]:
        """生成同契约 fallback 结果。"""
        selected, seed = deterministic_fallback(candidates, day, npc_id)
        # 多个无 routine 的候选可能共享默认时间；fallback 也必须满足完整计划的严格时间契约。
        next_minute = -1
        items: list[DailyScheduleItem] = []
        for candidate in selected:
            hour, minute = map(int, candidate.suggested_start_time.split(":"))
            proposed = hour * 60 + minute
            resolved = max(proposed, next_minute + 30)
            if resolved >= 24 * 60:
                break
            items.append(self._to_item(candidate, f"{resolved // 60:02d}:{resolved % 60:02d}", "fallback"))
            next_minute = resolved
        return tuple(items), seed

    @staticmethod
    def _to_item(candidate: ScheduleCandidate, start: str, source: str) -> DailyScheduleItem:
        """把内部候选转换为跨端稳定 DTO。"""
        return DailyScheduleItem(candidate.candidate_id, candidate.action_id, candidate.location_id, start, candidate.necessity, candidate.primary_group, candidate.groups, candidate.evidence_ids, candidate.target_person_id, source=source, miss_policy="request_replan" if candidate.necessity == "required" else "skip_next")

    @staticmethod
    def _prompt(context: BrainOperationContext, owner: NpcScheduleRequest, candidates: list[ScheduleCandidate]) -> str:
        """渲染紧凑输入，并要求只返回 candidate ID。"""
        return f"NPC={owner.npc_id}\nTIME={context.game_time.time_label()} WEATHER={context.game_time.weather}\nCONTEXT={owner.plan_context}\n{render_candidates(candidates)}\nReturn JSON array of 6-10 items: candidate_id, planned_start_time. Use only listed candidates and strictly increasing HH:MM."
