"""
Zone 邻近检测 — 纯函数，判断两个 location 是否在同一 Zone 或相邻 Zone。

规则:
  - street 与所有店铺、park、riverside 相邻
  - park 与 riverside 相邻
  - 店铺之间通过 street 间接相邻（不直接相邻）
"""
from typing import Optional

from .location_state import is_transit_location

# ── Zone 邻近映射 ──
_ADJACENCY: dict[str, set[str]] = {
    "street": {
        "flower_shop", "bakery", "bookstore", "wagashi",
        "police_box", "player_cafe", "park", "riverside",
    },
    "park":       {"riverside", "street"},
    "riverside":  {"park", "street"},
    # 店铺只与 street 直接相邻
    "flower_shop": {"street"},
    "bakery":      {"street"},
    "bookstore":   {"street"},
    "wagashi":     {"street"},
    "police_box":  {"street"},
    "player_cafe": {"street"},
}


def get_zone(location_id: str) -> str:
    """从 location_id 提取 zone 名。

    Args:
        location_id: e.g. ``"flower_shop.counter"``

    Returns:
        zone name, e.g. ``"flower_shop"``. 如果没有 ``.`` 则原样返回。
    """
    if "." in location_id:
        return location_id.split(".")[0]
    return location_id


def get_spot(location_id: str) -> Optional[str]:
    """从 location_id 提取 spot 名。

    Args:
        location_id: e.g. ``"flower_shop.counter"``

    Returns:
        spot name, e.g. ``"counter"``. 如果没有 ``.`` 则返回 None。
    """
    if "." in location_id:
        return location_id.split(".")[1]
    return None


def are_nearby(loc_a: str, loc_b: str) -> bool:
    """判断两个 location 是否在同一 Zone 或相邻 Zone。

    >>> are_nearby("flower_shop.counter", "flower_shop.doorway")
    True  # 同一 Zone
    >>> are_nearby("flower_shop.doorway", "street.crossroad")
    True  # 相邻 Zone
    >>> are_nearby("flower_shop.doorway", "bakery.counter")
    False  # 两个不同店铺，不直接相邻
    """
    if is_transit_location(loc_a) or is_transit_location(loc_b):
        return False

    zone_a = get_zone(loc_a)
    zone_b = get_zone(loc_b)

    if zone_a == zone_b:
        return True

    return zone_b in _ADJACENCY.get(zone_a, set())


def is_same_zone(loc_a: str, loc_b: str) -> bool:
    """判断两个 location 是否在同一 Zone（不含相邻）。"""
    if is_transit_location(loc_a) or is_transit_location(loc_b):
        return False
    return get_zone(loc_a) == get_zone(loc_b)


def get_nearby_npcs(npc_id: str, npc_locations: dict[str, str]) -> list[str]:
    """返回与指定 NPC 邻近的其他 NPC ID 列表。

    Args:
        npc_id: 当前 NPC ID
        npc_locations: ``{npc_id: location_id}`` 映射

    Returns:
        邻近 NPC ID 列表（按 ID 字母序）
    """
    my_loc = npc_locations.get(npc_id)
    if not my_loc or is_transit_location(my_loc):
        return []

    nearby = []
    for other_id, other_loc in npc_locations.items():
        if other_id == npc_id:
            continue
        if are_nearby(my_loc, other_loc):
            nearby.append(other_id)
    return sorted(nearby)


def get_nearby_npcs_in_same_zone(npc_id: str, npc_locations: dict[str, str]) -> list[str]:
    """返回与指定 NPC 在同一 Zone 的其他 NPC ID 列表。

    同一 Zone 意味着可以直接对话（不需要走到相邻 Zone）。
    """
    my_loc = npc_locations.get(npc_id)
    if not my_loc or is_transit_location(my_loc):
        return []

    my_zone = get_zone(my_loc)
    nearby = []
    for other_id, other_loc in npc_locations.items():
        if other_id == npc_id:
            continue
        if is_transit_location(other_loc):
            continue
        if get_zone(other_loc) == my_zone:
            nearby.append(other_id)
    return sorted(nearby)
