"""NPC 任务目录与 action-location affordance 校验。"""
from __future__ import annotations


class NpcTaskCatalog:
    """集中解析共享任务、地点标签和执行参数。"""

    WORK_ZONES_BY_NPC = {
        "sakura": "flower_shop",
        "chihaya": "bakery",
        "kazuha": "bookstore",
        "tatsunosuke": "wagashi",
    }

    def __init__(self, actions: dict, locations: dict):
        self.actions = actions
        self.locations = locations
        self._actions_by_id = {
            entry["id"]: entry
            for entries in actions.get("actions", {}).values()
            for entry in entries
        }
        self._affordances = actions.get("action_affordances", {})
        self._runtime_metadata = actions.get("task_runtime_metadata", {})
        self._location_ids = self._build_location_ids()

    @property
    def action_ids(self) -> set[str]:
        """返回所有可作为正式任务的 action ID。"""
        return set(self._actions_by_id).intersection(self._affordances)

    @property
    def location_ids(self) -> set[str]:
        """返回所有共享 spot 级 location ID。"""
        return set(self._location_ids)

    def validate_task(self, npc_id: str, action_id: str, location_id: str) -> tuple[bool, str]:
        """校验任务 ID、目标地点、NPC 限制和 spot affordance。"""
        action = self._actions_by_id.get(action_id)
        if action is None:
            return False, "unknown_action"
        if location_id not in self._location_ids:
            return False, "unknown_location"
        if action.get("npc_only") and action["npc_only"] != npc_id:
            return False, "npc_not_allowed"

        affordance = self._affordances.get(action_id)
        if not affordance:
            return False, "affordance_missing"
        allowed_npcs = set(affordance.get("allowed_npcs", []))
        if allowed_npcs and npc_id not in allowed_npcs:
            return False, "npc_not_allowed"
        if action_id.startswith("work_") and not self._is_own_work_zone(npc_id, location_id):
            return False, "npc_not_allowed"
        if affordance.get("anywhere"):
            return True, ""

        required_tags = set(affordance.get("location_tags", []))
        location_tags = self.location_tags(location_id)
        if required_tags and required_tags.isdisjoint(location_tags):
            return False, "location_not_afforded"
        return True, ""

    def movement_mode(self, action_id: str, requested: str = "") -> str:
        """解析任务移动方式，并限制为协议支持的固定集合。"""
        mode = requested or self._affordances.get(action_id, {}).get("movement_mode", "walk")
        return mode if mode in {"walk", "run", "none"} else "walk"

    def allowed_locations(self, npc_id: str, action_id: str) -> list[str]:
        """返回指定 NPC 执行某任务时可供计划层选择的全部合法地点。"""
        return [
            location_id
            for location_id in sorted(self._location_ids)
            if self.validate_task(npc_id, action_id, location_id)[0]
        ]

    def expected_duration(self, action_id: str, fallback: int = 0) -> int:
        """返回任务预计时长，仅用于前端表现参考和诊断。"""
        if fallback > 0:
            return fallback
        duration_range = self._actions_by_id.get(action_id, {}).get("duration_range_sec", [])
        if not duration_range:
            return 0
        return max(0, int(duration_range[0]))

    def task_runtime_metadata(self, action_id: str) -> dict[str, object]:
        """返回由共享目录声明的分段、完成、抢占和 Gameplay 持续量。"""
        if action_id not in self._actions_by_id:
            return {}
        metadata = self._runtime_metadata.get(action_id, {})
        return {
            "segment_id": metadata.get("segment_id", ""),
            "completion_policy_id": metadata.get("completion_policy_id", ""),
            "interrupt_policy": metadata.get("interrupt_policy", ""),
            "duration_gameplay_seconds": max(0, int(metadata.get("duration_gameplay_seconds", 0))),
            "lifecycle_action": bool(metadata.get("lifecycle_action", False)),
        }

    def validate_runtime_metadata(self, action_id: str) -> tuple[bool, str]:
        """验证正式任务的运行时元数据完整且只使用稳定枚举。"""
        metadata = self.task_runtime_metadata(action_id)
        if not metadata:
            return False, "unknown_action"
        if metadata["segment_id"] not in {"work", "rest", "both"}:
            return False, "invalid_segment_id"
        if metadata["completion_policy_id"] not in {
            "duration", "animation_event", "interaction_result", "state_condition", "segment_boundary"
        }:
            return False, "invalid_completion_policy_id"
        if metadata["interrupt_policy"] not in {
            "non_interruptible", "player_interruptible", "fully_interruptible"
        }:
            return False, "invalid_interrupt_policy"
        if metadata["completion_policy_id"] == "duration" and metadata["duration_gameplay_seconds"] <= 0:
            return False, "invalid_duration_gameplay_seconds"
        return True, ""

    def location_tags(self, location_id: str) -> set[str]:
        """组合显式 spot 标签、zone ID 和 spot ID，供 affordance 统一匹配。"""
        zone_id, spot_id = location_id.split(".", 1)
        explicit = self.locations.get("spot_tags", {}).get(location_id, [])
        return {zone_id, spot_id, *explicit}

    def _is_own_work_zone(self, npc_id: str, location_id: str) -> bool:
        """限制工作类任务只能发生在 NPC 自己负责的职业 zone。"""
        expected_zone = self.WORK_ZONES_BY_NPC.get(npc_id)
        if not expected_zone:
            return False
        zone_id = location_id.split(".", 1)[0]
        return zone_id == expected_zone

    def _build_location_ids(self) -> set[str]:
        """从共享 zone/spot 表生成稳定复合地点 ID。"""
        return {
            f"{zone_id}.{spot_id}"
            for zone_id, zone in self.locations.get("zones", {}).items()
            for spot_id in zone.get("spots", [])
        }
