"""
轻量项目规范检查脚本。

当前覆盖：
1. shared/ 稳定 ID 的 snake_case 校验
2. 复合 location_id、任务 affordance 与 routine 组合合法性校验
3. backend 配置文件名与内部主键一致性校验
4. Unity 位置配置与 shared/locations 的一致性校验
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SHARED_DIR = ROOT_DIR / "shared"
BACKEND_DIR = ROOT_DIR / "backend"
LOCATION_POSITIONS_PATH = ROOT_DIR / "Assets" / "Resources" / "Config" / "location_positions.json"
NPC_PROFILE_DIR = BACKEND_DIR / "config" / "npc_profiles"
LOCATION_PROFILE_DIR = BACKEND_DIR / "config" / "location_profiles"

SNAKE_CASE_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
COMPOSITE_ID_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*\.[a-z0-9]+(?:_[a-z0-9]+)*$")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def add_error(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_snake_case(value: str, label: str, errors: list[str]) -> None:
    if not SNAKE_CASE_RE.fullmatch(value):
        add_error(errors, f"{label} 不是 snake_case: {value}")


def validate_composite_id(value: str, label: str, errors: list[str]) -> None:
    if not COMPOSITE_ID_RE.fullmatch(value):
        add_error(errors, f"{label} 不是 <zone>.<spot> 复合 ID: {value}")


def build_location_ids(locations_data: dict, errors: list[str]) -> set[str]:
    zones = locations_data.get("zones", {})
    location_ids: set[str] = set()

    for zone_id, zone_data in zones.items():
        validate_snake_case(zone_id, "shared/locations zone_id", errors)
        spots = zone_data.get("spots", [])
        for spot_id in spots:
            validate_snake_case(spot_id, f"shared/locations spot_id ({zone_id})", errors)
            location_ids.add(f"{zone_id}.{spot_id}")

    return location_ids


def check_spot_tags(locations_data: dict, known_location_ids: set[str], errors: list[str]) -> None:
    """检查每个共享 location 都有可供任务 affordance 使用的 spot 标签。"""
    spot_tags = locations_data.get("spot_tags", {})
    for location_id, tags in spot_tags.items():
        validate_composite_id(location_id, "shared/locations spot_tags key", errors)
        if location_id not in known_location_ids:
            add_error(errors, f"shared/locations spot_tags 引用了不存在的位置: {location_id}")
        for tag in tags:
            validate_snake_case(tag, f"shared/locations spot tag ({location_id})", errors)
    for location_id in sorted(known_location_ids - set(spot_tags)):
        add_error(errors, f"shared/locations location 缺少 spot_tags: {location_id}")


def build_action_ids(actions_data: dict, errors: list[str]) -> set[str]:
    actions_by_category = actions_data.get("actions", {})
    action_ids: set[str] = set()

    for category_id, entries in actions_by_category.items():
        validate_snake_case(category_id, "shared/actions category", errors)
        for entry in entries:
            action_id = entry.get("id", "")
            validate_snake_case(action_id, f"shared/actions action_id ({category_id})", errors)
            action_ids.add(action_id)

            npc_only = entry.get("npc_only")
            if npc_only:
                validate_snake_case(npc_only, f"shared/actions npc_only ({action_id})", errors)

            requires = entry.get("requires")
            if requires and requires != "target_npc":
                validate_snake_case(requires, f"shared/actions requires ({action_id})", errors)

    return action_ids


def check_shared_actions(actions_data: dict, known_action_ids: set[str], errors: list[str]) -> None:
    """检查正式任务均有 affordance，且移动方式不是伪 action。"""
    forbidden_actions = {"walk_to", "run_to"}
    for action_id in sorted(forbidden_actions.intersection(known_action_ids)):
        add_error(errors, f"shared/actions 禁止把移动方式作为正式 action: {action_id}")

    affordances = actions_data.get("action_affordances", {})
    for action_id, affordance in affordances.items():
        if action_id not in known_action_ids:
            add_error(errors, f"action_affordances 引用了不存在的 action_id: {action_id}")
        mode = affordance.get("movement_mode", "walk")
        if mode not in {"walk", "run", "none"}:
            add_error(errors, f"action_affordances movement_mode 非法: {action_id} -> {mode}")


def location_tags(locations_data: dict, location_id: str) -> set[str]:
    """返回规范检查使用的显式与结构化地点标签。"""
    zone_id, spot_id = location_id.split(".", 1)
    return {zone_id, spot_id, *locations_data.get("spot_tags", {}).get(location_id, [])}


def check_shared_items(items_data: dict, known_zone_ids: set[str], errors: list[str]) -> None:
    allowed_non_zone_sources = {"vending", "shop", "found", "sakura_gift"}
    items = items_data.get("items", [])
    for item in items:
        item_id = item.get("id", "")
        validate_snake_case(item_id, "shared/items item_id", errors)

        source = item.get("source", "")
        if source not in allowed_non_zone_sources and source not in known_zone_ids:
            add_error(errors, f"shared/items source 未在已知 zone 或允许例外中声明: {item_id} -> {source}")


def check_npc_profiles(
    actions_data: dict,
    locations_data: dict,
    known_action_ids: set[str],
    known_location_ids: set[str],
    errors: list[str],
) -> set[str]:
    """检查 NPC 主键及 routine 的任务、地点和 affordance 组合。"""
    npc_ids: set[str] = set()

    for path in sorted(NPC_PROFILE_DIR.glob("*.json")):
        file_id = path.stem
        validate_snake_case(file_id, f"npc_profile 文件名 ({path.name})", errors)
        data = load_json(path)
        npc_id = data.get("npc_id", "")
        if npc_id != file_id:
            add_error(errors, f"npc_profile 文件名与 npc_id 不一致: {path.name} -> {npc_id}")
        npc_ids.add(file_id)

        daily_rhythm = data.get("daily_rhythm", {})
        for routine in daily_rhythm.get("routines", []):
            location_id = routine.get("location", "")
            action_id = routine.get("action", "")
            if location_id:
                validate_composite_id(location_id, f"npc_profile daily_rhythm location ({file_id})", errors)
            if action_id:
                validate_snake_case(action_id, f"npc_profile daily_rhythm action ({file_id})", errors)
            if action_id in {"walk_to", "run_to"}:
                add_error(errors, f"npc_profile routine 禁止使用移动 action: {file_id} -> {action_id}")
            if action_id not in known_action_ids:
                add_error(errors, f"npc_profile routine action 不存在: {file_id} -> {action_id}")
            if location_id not in known_location_ids:
                add_error(errors, f"npc_profile routine location 不存在: {file_id} -> {location_id}")

            affordance = actions_data.get("action_affordances", {}).get(action_id)
            if not affordance:
                add_error(errors, f"npc_profile routine 缺少 affordance: {file_id} -> {action_id}")
            elif not affordance.get("anywhere"):
                required = set(affordance.get("location_tags", []))
                if required and required.isdisjoint(location_tags(locations_data, location_id)):
                    add_error(
                        errors,
                        f"npc_profile routine action-location 不匹配: {file_id} -> {action_id}@{location_id}",
                    )
            allowed_npcs = set((affordance or {}).get("allowed_npcs", []))
            if allowed_npcs and file_id not in allowed_npcs:
                add_error(errors, f"npc_profile routine NPC 不允许执行任务: {file_id} -> {action_id}")

        for target_id in data.get("initial_bonds", {}).keys():
            if target_id != "player":
                validate_snake_case(target_id, f"npc_profile initial_bonds target ({file_id})", errors)

        for target_id in data.get("initial_impression_traits", {}).keys():
            if target_id != "player":
                validate_snake_case(target_id, f"npc_profile initial_impression_traits target ({file_id})", errors)

    return npc_ids


def check_location_profiles(known_zone_ids: set[str], errors: list[str]) -> None:
    for path in sorted(LOCATION_PROFILE_DIR.glob("*.json")):
        file_id = path.stem
        validate_snake_case(file_id, f"location_profile 文件名 ({path.name})", errors)
        data = load_json(path)
        location_id = data.get("location_id", "")
        if location_id != file_id:
            add_error(errors, f"location_profile 文件名与 location_id 不一致: {path.name} -> {location_id}")
        if file_id not in known_zone_ids:
            add_error(errors, f"location_profile 未在 shared/locations 中声明 zone: {file_id}")

        spots = data.get("spots", {})
        for spot_id in spots.keys():
            validate_snake_case(spot_id, f"location_profile spot_id ({file_id})", errors)


def check_location_positions(known_location_ids: set[str], errors: list[str]) -> None:
    data = load_json(LOCATION_POSITIONS_PATH)
    seen_ids: set[str] = set()

    for item in data.get("locations", []):
        location_id = item.get("id", "")
        validate_composite_id(location_id, "location_positions id", errors)
        if location_id not in known_location_ids:
            add_error(errors, f"location_positions 引用了 shared/locations 中不存在的 location_id: {location_id}")
        if location_id in seen_ids:
            add_error(errors, f"location_positions 出现重复 id: {location_id}")
        seen_ids.add(location_id)

    missing = sorted(known_location_ids - seen_ids)
    for location_id in missing:
        add_error(errors, f"location_positions 缺少 shared/locations 中的 location_id: {location_id}")


def main() -> int:
    errors: list[str] = []

    locations_data = load_json(SHARED_DIR / "locations.json")
    actions_data = load_json(SHARED_DIR / "actions.json")
    items_data = load_json(SHARED_DIR / "items.json")

    known_zone_ids = set(locations_data.get("zones", {}).keys())
    known_location_ids = build_location_ids(locations_data, errors)
    known_action_ids = build_action_ids(actions_data, errors)

    check_spot_tags(locations_data, known_location_ids, errors)
    check_shared_actions(actions_data, known_action_ids, errors)
    check_shared_items(items_data, known_zone_ids, errors)
    check_npc_profiles(
        actions_data,
        locations_data,
        known_action_ids,
        known_location_ids,
        errors,
    )
    check_location_profiles(known_zone_ids, errors)
    check_location_positions(known_location_ids, errors)

    if errors:
        print("规范检查失败：")
        for index, error in enumerate(errors, start=1):
            print(f"{index}. {error}")
        return 1

    print("规范检查通过：shared ID、profile 主键、location_positions 一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
