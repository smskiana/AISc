"""开局与跨日世界准备的统一编排 seam。"""
from __future__ import annotations

import asyncio
import inspect
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .operation_context import GameTimeSnapshot


PreparationReporter = Callable[["WorldPreparationSnapshot"], Awaitable[None] | None]


@dataclass(frozen=True)
class WorldPreparationResult:
    """表示一次已成功完成的世界准备结果。"""

    operation_id: str
    flow: str
    target_game_day: int
    weather: str
    game_time: GameTimeSnapshot
    npcs: list[dict]
    maintenance_status: str = "success"
    maintenance_failure_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorldPreparationSnapshot:
    """表示供协议和诊断读取的稳定世界准备状态。"""

    operation_id: str = ""
    flow: str = ""
    phase: str = ""
    is_active: bool = False
    progress_floor: float = 0.0
    failure_reason: str = ""
    target_game_day: int = 0


class WorldPreparationCoordinator:
    """串行编排冷启动、午夜结算和指定游戏日的日计划准备。"""

    def __init__(
        self,
        *,
        sqlite,
        state_manager,
        behavior,
        run_midnight_maintenance: Callable[[int], Awaitable[Any]],
    ) -> None:
        self._sqlite = sqlite
        self._state_manager = state_manager
        self._behavior = behavior
        self._run_midnight_maintenance = run_midnight_maintenance
        self._operation_lock = asyncio.Lock()
        self._snapshot = WorldPreparationSnapshot()
        self._completed_next_days: dict[int, WorldPreparationResult] = {}

    @property
    def snapshot(self) -> WorldPreparationSnapshot:
        """返回当前或最近一次世界准备的只读快照。"""
        return self._snapshot

    async def prepare_initial_world(
        self,
        mode: str,
        game_time: dict | None = None,
        report_stage: PreparationReporter | None = None,
    ) -> WorldPreparationResult:
        """准备新游戏或续玩世界，并保证当前游戏日的 NPC 计划已就绪。"""
        async with self._operation_lock:
            flow = "initial_world"
            frozen_time = self._initial_time(mode, game_time or {})
            operation_id = self._begin(flow, frozen_time.day)
            try:
                await self._report(report_stage, "initial_memory", 0.10)
                if mode == "NEW_GAME":
                    self._state_manager.cold_start()
                    self._behavior.reset_prepared_days()
                    self._completed_next_days.clear()
                await self._report(report_stage, "daily_plans", 0.55)
                await self._behavior.ensure_daily_plans(
                    frozen_time.day,
                    refresh_npc_day_state=False,
                    game_time=frozen_time,
                )
                await self._report(report_stage, "entering_world", 0.85)
                return self._complete(operation_id, flow, frozen_time)
            except Exception as error:
                self._fail(operation_id, flow, frozen_time.day, error)
                raise RuntimeError(f"world_preparation_failed:{type(error).__name__}") from error

    async def prepare_next_day(
        self,
        game_time: dict,
        report_stage: PreparationReporter | None = None,
    ) -> WorldPreparationResult:
        """完成午夜结算并准备次日 NPC 状态、天气与日计划。"""
        async with self._operation_lock:
            frozen_time = GameTimeSnapshot.from_dict(game_time)
            current_day = frozen_time.day
            target_day = current_day + 1
            next_time = GameTimeSnapshot(
                target_day, 8, 0, self._next_weather(frozen_time.weather), frozen_time.time_revision + 1
            )
            existing = self._completed_next_days.get(target_day)
            if existing is not None:
                return existing
            flow = "next_day"
            operation_id = self._begin(flow, target_day)
            try:
                await self._report(report_stage, "memory_settlement", 0.18)
                maintenance = await self._run_midnight_maintenance(current_day)
                await self._report(report_stage, "daily_plans", 0.70)
                await self._behavior.ensure_daily_plans(
                    target_day,
                    refresh_npc_day_state=True,
                    game_time=next_time,
                )
                await self._report(report_stage, "entering_world", 0.85)
                result = self._complete(
                    operation_id,
                    flow,
                    next_time,
                    maintenance_status=str(getattr(maintenance, "status", "success")),
                    maintenance_failure_reasons=tuple(getattr(maintenance, "failure_reasons", ())),
                )
                self._completed_next_days[target_day] = result
                return result
            except Exception as error:
                self._fail(operation_id, flow, target_day, error)
                raise RuntimeError(f"world_preparation_failed:{type(error).__name__}") from error

    def _initial_time(self, mode: str, game_time: dict) -> GameTimeSnapshot:
        """从 Unity 请求冻结开局时间；新游戏使用协议固定起点。"""
        if mode == "NEW_GAME":
            return GameTimeSnapshot(1, 8, 0, "sunny", 0)
        return GameTimeSnapshot.from_dict(game_time)

    def _begin(self, flow: str, target_game_day: int) -> str:
        """创建本次操作 ID 并发布活跃的初始快照。"""
        operation_id = f"world_prepare_{uuid.uuid4().hex}"
        self._snapshot = WorldPreparationSnapshot(
            operation_id=operation_id,
            flow=flow,
            phase="started",
            is_active=True,
            target_game_day=target_game_day,
        )
        return operation_id

    async def _report(self, reporter: PreparationReporter | None, phase: str, progress_floor: float) -> None:
        """更新状态并在存在协议观察者时发送阶段事件。"""
        self._snapshot = WorldPreparationSnapshot(
            operation_id=self._snapshot.operation_id,
            flow=self._snapshot.flow,
            phase=phase,
            is_active=True,
            progress_floor=progress_floor,
            target_game_day=self._snapshot.target_game_day,
        )
        if reporter is None:
            return
        result = reporter(self._snapshot)
        if inspect.isawaitable(result):
            await result

    def _complete(
        self,
        operation_id: str,
        flow: str,
        game_time: GameTimeSnapshot,
        maintenance_status: str = "success",
        maintenance_failure_reasons: tuple[str, ...] = (),
    ) -> WorldPreparationResult:
        """结束成功状态并读取即将发送给 Unity 的 NPC 快照。"""
        self._snapshot = WorldPreparationSnapshot(
            operation_id=operation_id,
            flow=flow,
            phase="complete",
            is_active=False,
            progress_floor=1.0,
            target_game_day=game_time.day,
        )
        npcs = self._sqlite.fetchall(
            "SELECT npc_id, emotion, energy, sociability, current_location, "
            "current_action, is_first_encounter, current_need FROM npc_states"
        )
        return WorldPreparationResult(
            operation_id=operation_id,
            flow=flow,
            target_game_day=game_time.day,
            weather=game_time.weather,
            game_time=game_time,
            npcs=[dict(npc) for npc in npcs],
            maintenance_status=maintenance_status,
            maintenance_failure_reasons=maintenance_failure_reasons,
        )

    @staticmethod
    def _next_weather(current_weather: str) -> str:
        """在无全局时钟写入的前提下生成次日确定性天气回退。"""
        return "rainy" if current_weather == "sunny" else "sunny"

    def _fail(self, operation_id: str, flow: str, target_game_day: int, error: Exception) -> None:
        """保留稳定失败原因，避免向协议泄漏供应商或堆栈细节。"""
        self._snapshot = WorldPreparationSnapshot(
            operation_id=operation_id,
            flow=flow,
            phase="failed",
            is_active=False,
            failure_reason=f"world_preparation_failed:{type(error).__name__}",
            target_game_day=target_game_day,
        )
