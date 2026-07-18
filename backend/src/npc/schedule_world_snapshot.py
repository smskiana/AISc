"""Unity 权威日程物理快照的只读 DTO 与有界缓存。"""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

_STATES = {"open", "closed", "unknown"}
_REACHABLE = {"reachable", "unreachable", "unknown"}
_AVAILABLE = {"available", "unavailable", "unknown"}


@dataclass(frozen=True)
class ScheduleWorldSnapshot:
    """同一批日程规划共享的 Unity 权威事实。"""
    snapshot_id: str
    time_revision: int
    world_revision: int
    game_time: dict
    weather: str
    locations: dict[str, dict]
    spots: dict[str, dict]
    npcs: dict[str, dict]

    @classmethod
    def from_dict(cls, payload: dict) -> "ScheduleWorldSnapshot":
        """解析有限枚举，缺失动态事实始终保留 unknown。"""
        snapshot_id = str(payload.get("snapshot_id") or "")
        if not snapshot_id:
            raise ValueError("schedule_snapshot_id_missing")
        time_revision, world_revision = int(payload.get("time_revision", -1)), int(payload.get("world_revision", -1))
        if time_revision < 0 or world_revision < 0:
            raise ValueError("schedule_snapshot_revision_invalid")
        locations = {str(x.get("location_id")): {**x, "open_state": x.get("open_state") if x.get("open_state") in _STATES else "unknown", "reachable_state": x.get("reachable_state") if x.get("reachable_state") in _REACHABLE else "unknown"} for x in payload.get("locations", []) if x.get("location_id")}
        spots = {str(x.get("spot_id")): {**x, "availability": x.get("availability") if x.get("availability") in _AVAILABLE else "unknown"} for x in payload.get("spots", []) if x.get("spot_id")}
        npcs = {str(x.get("npc_id")): dict(x) for x in payload.get("npcs", []) if x.get("npc_id")}
        return cls(snapshot_id, time_revision, world_revision, dict(payload.get("game_time") or {}), str(payload.get("weather") or "unknown"), locations, spots, npcs)

    def physical_state_for(self, npc_id: str) -> dict:
        """投影单 owner 可消费的物理状态，不伪造可用性。"""
        state = dict(self.npcs.get(npc_id) or {})
        state.update({"snapshot_id": self.snapshot_id, "time_revision": self.time_revision, "world_revision": self.world_revision, "weather": self.weather, "locations": self.locations, "spots": self.spots})
        return state


class ScheduleWorldSnapshotStore:
    """按 ID 保存最近 Unity 快照，拒绝倒退版本。"""
    def __init__(self, limit: int = 8):
        self._limit, self._items, self._latest, self._lock = limit, {}, None, Lock()

    def put(self, snapshot: ScheduleWorldSnapshot) -> None:
        """原子保存单调快照。"""
        with self._lock:
            if self._latest and (snapshot.time_revision < self._latest.time_revision or snapshot.world_revision < self._latest.world_revision):
                raise ValueError("schedule_snapshot_revision_stale")
            self._items[snapshot.snapshot_id] = snapshot
            self._latest = snapshot
            while len(self._items) > self._limit: self._items.pop(next(iter(self._items)))

    def require(self, snapshot_id: str, time_revision: int, world_revision: int) -> ScheduleWorldSnapshot:
        """取得精确版本，拒绝缺失、过期或不一致引用。"""
        with self._lock: snapshot = self._items.get(snapshot_id)
        if snapshot is None: raise ValueError("schedule_snapshot_missing")
        if snapshot.time_revision != time_revision or snapshot.world_revision != world_revision: raise ValueError("schedule_snapshot_version_mismatch")
        return snapshot

    def require_latest(self) -> ScheduleWorldSnapshot:
        """仅供开局批次取得最近已接收的完整 Unity 快照。"""
        with self._lock: snapshot = self._latest
        if snapshot is None: raise ValueError("schedule_snapshot_missing")
        return snapshot
