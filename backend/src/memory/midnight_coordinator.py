"""午夜维护的并发编排、写入边界与结构化诊断。"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict, dataclass, field
from threading import Lock
from typing import Awaitable, Callable

from ..npc.player_impression_refresh import PlayerImpressionBatchResult, PlayerImpressionRefresher


@dataclass
class MidnightMaintenanceResult:
    """描述一次午夜维护的阶段、结果、失败和耗时。"""

    operation_id: str = ""
    status: str = "running"
    phase: str = "idle"
    target_count: int = 5
    direction_source: str = "nightly_fixed_player"
    llm_direction_calls: int = 0
    retrieval_trace_ids: dict[str, str] = field(default_factory=dict)
    impression_planned_count: int = 0
    impression_success_count: int = 0
    impression_fallback_count: int = 0
    impression_failed_owner_ids: list[str] = field(default_factory=list)
    extraction_event_owner_count: int = 0
    extraction_success_count: int = 0
    extraction_failure_count: int = 0
    extraction_invalid_node_count: int = 0
    extraction_invalid_edge_count: int = 0
    extraction_failed_owner_ids: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)
    stage_elapsed_sec: dict[str, float] = field(default_factory=dict)
    parallel_wall_sec: float = 0.0
    total_elapsed_sec: float = 0.0


class MidnightSnapshotStore:
    """保存当前及最近一次午夜结构化快照。"""

    def __init__(self):
        """初始化线程安全快照容器。"""
        self._lock = Lock()
        self._snapshot = MidnightMaintenanceResult()

    def update(self, snapshot: MidnightMaintenanceResult) -> None:
        """原子替换诊断快照。"""
        with self._lock:
            self._snapshot = snapshot

    def snapshot(self) -> dict:
        """返回可序列化的午夜快照副本。"""
        with self._lock:
            return asdict(self._snapshot)


midnight_snapshot_store = MidnightSnapshotStore()


class MidnightCoordinator:
    """协调午夜各阶段，并隔离 LLM 工作线程与 SQLite 印象提交。"""

    def __init__(
        self,
        impression_refresher: PlayerImpressionRefresher,
        run_edge_decay: Callable[[], None],
        run_event_extraction: Callable[[], Awaitable[dict]],
        run_graph_evolution: Callable[[], Awaitable[None]],
        run_short_term_cleanup: Callable[[], None],
        snapshot_store: MidnightSnapshotStore | None = None,
    ):
        """注入各阶段的稳定业务入口。"""
        self.impressions = impression_refresher
        self.run_edge_decay = run_edge_decay
        self.run_event_extraction = run_event_extraction
        self.run_graph_evolution = run_graph_evolution
        self.run_short_term_cleanup = run_short_term_cleanup
        self.snapshots = snapshot_store or midnight_snapshot_store

    async def run(self, game_day: int) -> MidnightMaintenanceResult:
        """执行路由冻结、双重阶段并发、演化、提交、刷新与清理。"""
        started = time.perf_counter()
        result = MidnightMaintenanceResult(
            operation_id=f"midnight_{uuid.uuid4().hex[:12]}",
            target_count=len(self.impressions.npc_ids),
        )
        self._publish(result, "edge_decay")
        await self._timed(result, "edge_decay", asyncio.to_thread(self.run_edge_decay))

        self._publish(result, "prepare_player_impression_routes")
        inputs = await self._timed(
            result,
            "prepare_player_impression_routes",
            asyncio.to_thread(self.impressions.prepare_inputs, game_day),
        )
        result.retrieval_trace_ids = {item.owner_id: item.retrieval_trace_id for item in inputs}

        self._publish(result, "parallel_heavy_stages")
        parallel_started = time.perf_counter()
        branch_results = await asyncio.gather(
            asyncio.to_thread(self.impressions.generate, inputs),
            self.run_event_extraction(),
            return_exceptions=True,
        )
        result.parallel_wall_sec = time.perf_counter() - parallel_started
        impression_batch = self._consume_impression_result(result, branch_results[0], inputs)
        self._consume_extraction_result(result, branch_results[1])

        self._publish(result, "graph_evolution")
        await self._timed(result, "graph_evolution", self.run_graph_evolution())

        self._publish(result, "commit_player_impressions")
        await self._timed(
            result,
            "commit_player_impressions",
            asyncio.to_thread(self.impressions.commit, impression_batch, game_day),
        )

        self._publish(result, "refresh_next_day_baselines")
        await self._timed(
            result,
            "refresh_next_day_baselines",
            asyncio.to_thread(self.impressions.refresh_next_day_baselines, game_day),
        )

        self._publish(result, "stm_cleanup")
        await self._timed(result, "stm_cleanup", asyncio.to_thread(self.run_short_term_cleanup))
        result.status = "partial_failure" if result.failure_reasons else "success"
        result.phase = "complete"
        result.total_elapsed_sec = time.perf_counter() - started
        self.snapshots.update(result)
        return result

    async def _timed(self, result: MidnightMaintenanceResult, name: str, awaitable):
        """执行单个阶段并记录墙钟耗时。"""
        started = time.perf_counter()
        try:
            return await awaitable
        except Exception as error:
            result.status = "failed"
            result.failure_reasons.append(f"{name}:{error}")
            result.total_elapsed_sec = time.perf_counter() - started
            self.snapshots.update(result)
            raise
        finally:
            result.stage_elapsed_sec[name] = time.perf_counter() - started

    def _consume_impression_result(self, result, branch_result, inputs) -> PlayerImpressionBatchResult:
        """收口玩家印象分支结果，并在分支级异常时生成全量 fallback。"""
        if isinstance(branch_result, PlayerImpressionBatchResult):
            batch = branch_result
        else:
            reason = str(branch_result)
            outputs = []
            for item in inputs:
                outputs.append(self.impressions._generate_fallback_output(item, reason))
            batch = PlayerImpressionBatchResult(
                outputs=outputs,
                planned_count=len(inputs),
                fallback_count=len(inputs),
                failed_owner_ids=[item.owner_id for item in inputs],
            )
        result.impression_planned_count = batch.planned_count
        result.impression_success_count = batch.success_count
        result.impression_fallback_count = batch.fallback_count
        result.impression_failed_owner_ids = list(batch.failed_owner_ids)
        result.stage_elapsed_sec["generate_player_impressions"] = batch.elapsed_sec
        if batch.fallback_count:
            result.failure_reasons.append("player_impression_fallback")
        return batch

    @staticmethod
    def _consume_extraction_result(result: MidnightMaintenanceResult, branch_result) -> None:
        """收口事件提取分支的成功、失败和非法输出计数。"""
        if isinstance(branch_result, Exception):
            result.extraction_failure_count = 1
            result.failure_reasons.append(f"event_extraction:{branch_result}")
            return
        result.extraction_event_owner_count = int(branch_result.get("event_owner_count", 0))
        result.extraction_success_count = int(branch_result.get("success_count", 0))
        result.extraction_failure_count = int(branch_result.get("failure_count", 0))
        result.extraction_invalid_node_count = int(branch_result.get("invalid_node_count", 0))
        result.extraction_invalid_edge_count = int(branch_result.get("invalid_edge_count", 0))
        result.extraction_failed_owner_ids = list(branch_result.get("failed_owner_ids", []))
        result.stage_elapsed_sec["event_extraction"] = float(branch_result.get("elapsed_sec", 0.0))
        if result.extraction_failure_count:
            result.failure_reasons.append("event_extraction_partial_failure")

    def _publish(self, result: MidnightMaintenanceResult, phase: str) -> None:
        """更新运行阶段并发布结构化快照。"""
        result.phase = phase
        self.snapshots.update(result)
