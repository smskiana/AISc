"""不可变 brain operation 时间与世界版本契约。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameTimeSnapshot:
    """保存一次 operation 开始时由 Unity 提供的冻结时间。"""

    day: int
    hour: int
    minute: int
    weather: str = "sunny"
    time_revision: int = 0

    @classmethod
    def from_dict(cls, value: dict) -> "GameTimeSnapshot":
        """严格解析 Unity 时间快照并拒绝越界值。"""
        snapshot = cls(
            day=int(value.get("day", 0)),
            hour=int(value.get("hour", -1)),
            minute=int(value.get("minute", -1)),
            weather=str(value.get("weather") or "sunny"),
            time_revision=int(value.get("time_revision", 0)),
        )
        if snapshot.day < 1 or not 0 <= snapshot.hour <= 23 or not 0 <= snapshot.minute <= 59:
            raise ValueError("invalid_game_time_snapshot")
        return snapshot

    def time_label(self) -> str:
        """返回业务 Prompt 和记忆使用的稳定时间标签。"""
        return f"第{self.day}天 {self.hour:02d}:{self.minute:02d}"


@dataclass(frozen=True)
class BrainOperationContext:
    """绑定 operation ID、冻结时间与输入世界版本。"""

    operation_id: str
    game_time: GameTimeSnapshot
    world_revision: int

