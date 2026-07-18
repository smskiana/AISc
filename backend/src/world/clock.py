"""
游戏时钟 — 三速时间 + 午夜检测。
"""
class GameClock:
    """游戏内时间管理器"""

    def __init__(self):
        self.day: int = 1
        self.hour: int = 8
        self.minute: int = 0
        self.weather: str = "sunny"

    def set_state(self, day: int, hour: int, minute: int, weather: str = "sunny"):
        """从存档恢复"""
        self.day = day
        self.hour = hour
        self.minute = minute
        self.weather = weather

    def to_dict(self) -> dict:
        return {
            "day": self.day,
            "hour": self.hour,
            "minute": self.minute,
            "weather": self.weather,
        }

    def time_str(self) -> str:
        return f"第{self.day}天 {self.hour:02d}:{self.minute:02d}"

    def time_str_en(self) -> str:
        """英文格式（SQL 查询用）"""
        return f"Day {self.day}, {self.hour:02d}:{self.minute:02d}"

    def set_state_from_request(self, state: dict) -> None:
        """仅在一次请求开始时应用 Unity 冻结时间，不启动推进或业务回调。"""
        self.set_state(
            int(state.get("day") or 1),
            int(state.get("hour") or 0),
            int(state.get("minute") or 0),
            str(state.get("weather") or "sunny"),
        )

# 全局游戏时钟
game_clock = GameClock()
