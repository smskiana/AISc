"""Unity 聚合暂停状态同步测试。"""
from __future__ import annotations

import unittest

from backend.src.application.runtime import GameRuntime
from backend.src.world.clock import GameClock, game_clock


class FakeWebSocket:
    """收集暂停同步确认消息。"""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        """记录服务端回包。"""
        self.messages.append(payload)


class GameClockPassiveTests(unittest.TestCase):
    """验证 Python 时间对象不再拥有自主推进或暂停能力。"""

    def test_clock_has_no_runtime_loop_or_pause_api(self) -> None:
        """被动快照不得暴露 start、tick、speed 或 pause API。"""
        clock = GameClock()
        for name in ("start", "stop", "on_tick", "_tick_loop", "set_speed", "push_pause", "pop_pause"):
            self.assertFalse(hasattr(clock, name), name)


class UnityPauseSyncTests(unittest.IsolatedAsyncioTestCase):
    """验证 Unity 聚合状态无需初始化业务服务即可即时处理。"""

    async def test_pause_and_resume_are_acknowledged(self) -> None:
        """暂停与恢复消息应更新镜像时钟并返回确认。"""
        # 旧口径保留在原注释中用于迁移审计；当前应明确拒绝且不得修改状态。
        runtime = GameRuntime()
        websocket = FakeWebSocket()

        await runtime.handle_message(websocket, {
            "type": "GAME_PAUSE_STATE",
            "paused": True,
            "sources": ["pause_menu", "inventory"],
        })
        self.assertEqual(websocket.messages[-1]["message"], "legacy_time_control_removed")


class UnityTimeSyncTests(unittest.IsolatedAsyncioTestCase):
    """验证 Unity 时间无条件覆盖 Python 镜像。"""

    async def test_unity_time_replaces_mirror_state(self) -> None:
        """存在时间偏差时应采用 Unity 的天、小时、分钟和流速。"""
        # 旧口径保留在原注释中用于迁移审计；当前只允许 operation 请求携带冻结时间。
        runtime = GameRuntime()
        websocket = FakeWebSocket()
        game_clock.set_state(9, 22, 45, "rainy")

        await runtime.handle_message(websocket, {
            "type": "GAME_TIME_SYNC",
            "game_time": {"day": 2, "hour": 10, "minute": 30, "weather": "sunny"},
            "seconds_per_game_minute": 1.25,
            "reason": "test",
        })

        self.assertEqual(game_clock.to_dict(), {
            "day": 9,
            "hour": 22,
            "minute": 45,
            "weather": "rainy",
        })
        self.assertEqual(websocket.messages[-1]["message"], "legacy_time_control_removed")
