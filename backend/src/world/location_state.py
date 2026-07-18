"""运行时位置状态语义。"""
from __future__ import annotations


TRANSIT_LOCATION_PREFIX = "__transit__"


def build_transit_location(npc_id: str, request_id: str) -> str:
    """为一次 NPC 移动生成不属于任何地区的唯一途中位置。"""
    return f"{TRANSIT_LOCATION_PREFIX}:{npc_id}:{request_id}"


def is_transit_location(location_id: str | None) -> bool:
    """判断位置是否为移动途中内部标记。"""
    return bool(location_id) and str(location_id).startswith(f"{TRANSIT_LOCATION_PREFIX}:")
