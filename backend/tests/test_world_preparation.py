"""世界准备协调器的成功、幂等和失败回归测试。"""
from __future__ import annotations

import unittest

from backend.src.application.world_preparation import WorldPreparationCoordinator


class FakeSqlite:
    """为协调器测试提供固定 NPC 快照。"""

    def __init__(self):
        self.has_npcs = False

    def fetchone(self, query):
        if "COUNT" in query:
            return {"cnt": 5 if self.has_npcs else 0}
        return None

    def fetchall(self, query):
        return [{"npc_id": "sakura", "current_location": "flower_shop.counter"}]


class FakeStateManager:
    """记录冷启动调用次数。"""

    def __init__(self):
        self.cold_starts = 0

    def cold_start(self):
        self.cold_starts += 1


class FakeBehavior:
    """记录按日准备调用并可模拟失败。"""

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def reset_prepared_days(self):
        """模拟新世界切换时清除行为缓存。"""
        pass

    async def ensure_daily_plans(self, day, refresh_npc_day_state, game_time=None):
        self.calls.append((day, refresh_npc_day_state))
        if self.fail:
            raise ValueError("planned failure")


class WorldPreparationTests(unittest.IsolatedAsyncioTestCase):
    """验证世界准备的成功终态、重复请求和失败状态。"""

    def make_coordinator(self, behavior=None):
        self.sqlite = FakeSqlite()
        self.state = FakeStateManager()
        self.maintenance_calls = 0

        async def maintenance(_game_day):
            self.maintenance_calls += 1

        return WorldPreparationCoordinator(
            sqlite=self.sqlite,
            state_manager=self.state,
            behavior=behavior or FakeBehavior(),
            run_midnight_maintenance=maintenance,
        )

    async def test_new_game_prepares_plans_before_success(self):
        behavior = FakeBehavior()
        coordinator = self.make_coordinator(behavior)
        snapshots = []

        result = await coordinator.prepare_initial_world(
            "NEW_GAME", report_stage=lambda snapshot: snapshots.append(snapshot)
        )

        self.assertEqual(1, self.state.cold_starts)
        self.assertEqual([(1, False)], behavior.calls)
        self.assertEqual(
            ["initial_memory", "daily_plans", "entering_world"],
            [snapshot.phase for snapshot in snapshots],
        )
        self.assertTrue(all(snapshot.target_game_day == 1 for snapshot in snapshots))
        self.assertEqual("complete", coordinator.snapshot.phase)
        self.assertFalse(coordinator.snapshot.is_active)
        self.assertTrue(result.operation_id.startswith("world_prepare_"))

    async def test_repeated_next_day_request_does_not_replan_same_day(self):
        behavior = FakeBehavior()
        coordinator = self.make_coordinator(behavior)

        game_time = {"day": 1, "hour": 23, "minute": 59, "weather": "sunny", "time_revision": 2}
        await coordinator.prepare_next_day(game_time)
        await coordinator.prepare_next_day(game_time)

        self.assertEqual([(2, True)], behavior.calls)
        self.assertEqual(1, self.maintenance_calls)

    async def test_failure_keeps_stable_failure_reason(self):
        coordinator = self.make_coordinator(FakeBehavior(fail=True))

        with self.assertRaisesRegex(RuntimeError, "world_preparation_failed:ValueError"):
            await coordinator.prepare_initial_world("NEW_GAME")

        self.assertFalse(coordinator.snapshot.is_active)
        self.assertEqual("failed", coordinator.snapshot.phase)
        self.assertEqual("world_preparation_failed:ValueError", coordinator.snapshot.failure_reason)
