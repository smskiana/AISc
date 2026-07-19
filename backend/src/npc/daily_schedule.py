"""NPC 日程深模块的公开契约与编排。"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable

from ..application.operation_context import BrainOperationContext
from .schedule_candidates import ScheduleCandidate, ScheduleCandidateBuilder, apply_memory_scores, deterministic_fallback
from .schedule_diagnostics import ScheduleDiagnostics, ScheduleOwnerTrace
from .schedule_memory_evidence import ScheduleMemoryEvidenceProvider
from .schedule_prompt_adapter import parse_selection, render_candidates
from .schedule_validation import validate_selection


@dataclass(frozen=True)
class NpcPlannedTask:
    """跨端持久化的不含精确时间点的计划任务。"""

    candidate_id: str
    action_id: str
    location_id: str
    segment_id: str
    completion_policy_id: str
    interrupt_policy: str
    duration_gameplay_seconds: int
    necessity: str
    primary_group: str
    groups: tuple[str, ...]
    evidence_ids: tuple[str, ...] = ()
    target_person_id: str = ""
    source: str = "fallback"


@dataclass(frozen=True)
class NpcPlanSegment:
    """定义稳定的日计划阶段边界。"""

    segment_id: str
    starts_at: str
    ends_at: str
    boundary_policy: str


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
    plan_revision: int
    planner_version: str
    segments: tuple[NpcPlanSegment, ...]
    work_tasks: tuple[NpcPlannedTask, ...]
    rest_tasks: tuple[NpcPlannedTask, ...]
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
    remaining_schedule: tuple[NpcPlannedTask, ...]


class DailySchedulePlanner:
    """统一执行候选构建、LLM 选择、校验、超时与 fallback。"""

    PLANNER_VERSION = "daily_schedule_v2"

    def __init__(self, catalog, llm_call: Callable[[list[dict]], Awaitable[str]], timeout_seconds: float = 120.0, diagnostics: ScheduleDiagnostics | None = None, memory_retrieve=None):
        self._builder = ScheduleCandidateBuilder(catalog)
        self._llm_call = llm_call
        self._timeout_seconds = timeout_seconds
        self.diagnostics = diagnostics or ScheduleDiagnostics()
        self._memory_evidence = ScheduleMemoryEvidenceProvider(memory_retrieve) if memory_retrieve else None

    async def prepare_day(self, request: DailyScheduleBatchRequest) -> DailyScheduleBatchResult:
        """并发规划所有 owner，并为每个 owner 独立收口。"""
        results = await asyncio.gather(*(self._prepare_owner(request.context, owner) for owner in request.owners))
        return DailyScheduleBatchResult(request.context.operation_id, tuple(results))

    async def replan_after_interaction(self, request: InteractionReplanRequest) -> NpcScheduleResult:
        """仅对有效互动基于 base revision 生成完整替换结果。"""
        if request.end_reason != "completed" or not request.interaction_summary.strip():
            return self._skipped_result(request, "interaction_not_eligible")
        return await self._prepare_owner(request.context, request.owner)

    async def replan_after_runtime_recovery(self, request: InteractionReplanRequest) -> NpcScheduleResult:
        """为窗口错过、执行失败或取消生成日程恢复替换，不伪装为互动完成。"""
        if not request.interaction_type.startswith("schedule_"):
            return self._skipped_result(request, "runtime_recovery_type_invalid")
        return await self._prepare_owner(request.context, request.owner)

    async def _prepare_owner(self, context: BrainOperationContext, owner: NpcScheduleRequest) -> NpcScheduleResult:
        """执行单 owner operation，超时后隔离迟到供应商结果。"""
        operation_id = context.operation_id if owner.base_schedule_revision > 0 else f"{context.operation_id}:{owner.npc_id}:{uuid.uuid4().hex[:8]}"
        started = time.perf_counter()
        candidates, rejection_counts = self._builder.build(owner.npc_id, list(owner.routines), owner.physical_state)
        trace = ScheduleOwnerTrace(operation_id, owner.npc_id, context.game_time.day, candidate_count=len(candidates))
        trace.rejection_counts = rejection_counts
        for candidate in candidates:
            trace.candidate_group_counts[candidate.primary_group] = trace.candidate_group_counts.get(candidate.primary_group, 0) + 1
        if self._memory_evidence:
            trace.execution_phase = "memory_evidence"
            evidence, memory_stats = self._memory_evidence.enrich(owner.npc_id, candidates, context.game_time.time_label(), str(owner.physical_state.get("current_location_id") or ""))
            candidates = apply_memory_scores(candidates, evidence)
            trace.memory_stats = memory_stats
            trace.evidence_ids = sorted({evidence_id for candidate in candidates for evidence_id in candidate.evidence_ids})[:100]
        trace.execution_phase = "provider_call"
        self.diagnostics.publish(trace)
        try:
            messages = [{"role": "user", "content": self._prompt(context, owner, candidates)}]
            raw = await asyncio.wait_for(self._llm_call(messages), timeout=self._timeout_seconds)
            by_id = {item.candidate_id: item for item in candidates}
            selected = parse_selection(raw, by_id)
            validate_selection(selected, candidates)
            trace.validation_status = "accepted"
            work_tasks = tuple(self._to_item(by_id[candidate_id], "llm") for candidate_id in selected["work"])
            rest_tasks = tuple(self._to_item(by_id[candidate_id], "llm") for candidate_id in selected["rest"])
            if not work_tasks and not rest_tasks:
                raise ValueError("empty_schedule")
            trace.status = "success"
        except asyncio.TimeoutError:
            work_tasks, rest_tasks, seed, fallback_reasons = self._fallback(candidates, context.game_time.day, owner.npc_id)
            trace.status, trace.failure_reason, trace.fallback_seed = "fallback", "provider_timeout", seed
            trace.validation_status = "provider_timeout"
            trace.failure_detail = "provider_timeout"
            trace.provider_call_not_cancelled = True
            trace.fallback_reasons = dict(list(fallback_reasons.items())[:50])
        except Exception as error:
            work_tasks, rest_tasks, seed, fallback_reasons = self._fallback(candidates, context.game_time.day, owner.npc_id)
            failure_code = str(error) if isinstance(error, ValueError) and str(error) else "planner_internal_error"
            trace.status, trace.failure_reason, trace.fallback_seed = "fallback", failure_code, seed
            trace.validation_status = "rejected"
            trace.failure_detail = str(error)[:200]
            trace.fallback_reasons = dict(list(fallback_reasons.items())[:50])
        trace.selected_count = len(work_tasks) + len(rest_tasks)
        trace.elapsed_sec = time.perf_counter() - started
        trace.execution_phase = "completed"
        self.diagnostics.publish(trace)
        return NpcScheduleResult(operation_id, owner.npc_id, context.game_time.day, owner.base_schedule_revision + 1, self.PLANNER_VERSION, self._segments(), work_tasks, rest_tasks, trace.status, trace.failure_reason)

    def _fallback(self, candidates: list[ScheduleCandidate], day: int, npc_id: str) -> tuple[tuple[NpcPlannedTask, ...], tuple[NpcPlannedTask, ...], int, dict[str, str]]:
        """生成同契约 fallback 结果。"""
        selected, seed, reasons = deterministic_fallback(candidates, day, npc_id)
        selection = {
            "work": [item.candidate_id for item in selected if item.segment_id == "work"],
            "rest": [item.candidate_id for item in selected if item.segment_id == "rest"],
        }
        validate_selection(selection, candidates)
        by_id = {item.candidate_id: item for item in candidates}
        return (tuple(self._to_item(by_id[item], "fallback") for item in selection["work"]),
                tuple(self._to_item(by_id[item], "fallback") for item in selection["rest"]), seed, reasons)

    @staticmethod
    def _to_item(candidate: ScheduleCandidate, source: str) -> NpcPlannedTask:
        """把内部候选转换为跨端稳定 DTO。"""
        return NpcPlannedTask(candidate.candidate_id, candidate.action_id, candidate.location_id, candidate.segment_id, candidate.completion_policy_id, candidate.interrupt_policy, candidate.duration_gameplay_seconds, candidate.necessity, candidate.primary_group, candidate.groups, candidate.evidence_ids, candidate.target_person_id, source)

    @staticmethod
    def _prompt(context: BrainOperationContext, owner: NpcScheduleRequest, candidates: list[ScheduleCandidate]) -> str:
        """渲染紧凑输入，并要求只返回 candidate ID。"""
        required_groups = sorted({item.required_group_id for item in candidates if item.required_group_id})
        return f"NPC={owner.npc_id}\nDAY={context.game_time.day} WEATHER={context.game_time.weather}\nCONTEXT={owner.plan_context}\nREQUIRED_GROUPS={required_groups}\n{render_candidates(candidates)}\nReturn one JSON object with work_tasks[] and rest_tasks[]. Each array contains only candidate ID strings in execution order. Do not return times, durations, completion conditions, movement, or failure policies."

    @staticmethod
    def _segments() -> tuple[NpcPlanSegment, ...]:
        """返回协议固定的工作与休息阶段定义。"""
        return (NpcPlanSegment("work", "08:00", "17:00", "active_task_continues"),
                NpcPlanSegment("rest", "17:00", "24:00", "force_terminal_at_day_end"))

    def _skipped_result(self, request: InteractionReplanRequest, reason: str) -> NpcScheduleResult:
        """把兼容调用稳定收口为不替换当前计划的结果。"""
        work = tuple(item for item in request.remaining_schedule if item.segment_id == "work")
        rest = tuple(item for item in request.remaining_schedule if item.segment_id == "rest")
        return NpcScheduleResult(request.context.operation_id, request.owner.npc_id, request.context.game_time.day,
                                 request.owner.base_schedule_revision, self.PLANNER_VERSION, self._segments(), work, rest,
                                 "skipped", reason)
