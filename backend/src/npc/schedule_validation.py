"""日程选择的最终硬约束校验。"""
from __future__ import annotations


def validate_selection(selected, candidates) -> None:
    """验证归属、数量、必要项、覆盖、时间与物理合法性，任一失败整体拒绝。"""
    by_id = {item.candidate_id: item for item in candidates}
    if not selected:
        raise ValueError("empty_schedule")
    minimum = min(6, len(candidates))
    if not minimum <= len(selected) <= 10:
        raise ValueError("schedule_item_count_out_of_range")
    ids = [candidate_id for candidate_id, _ in selected]
    if len(ids) != len(set(ids)) or any(candidate_id not in by_id for candidate_id in ids):
        raise ValueError("candidate_ownership_invalid")
    required = {item.candidate_id for item in candidates if item.necessity == "required"}
    if not required.issubset(ids):
        raise ValueError("required_candidate_missing")
    groups = {by_id[candidate_id].primary_group for candidate_id in ids}
    required_groups = {item.primary_group for item in candidates if item.necessity == "required"}
    if not required_groups.issubset(groups):
        raise ValueError("required_group_missing")
    previous = -1
    for candidate_id, label in selected:
        hour, minute = map(int, label.split(":"))
        current = hour * 60 + minute
        candidate = by_id[candidate_id]
        if current <= previous:
            raise ValueError("non_monotonic_schedule")
        if not candidate.legal_start_minute <= current <= candidate.legal_end_minute:
            raise ValueError("candidate_time_window_invalid")
        if candidate.business_state in {"closed", "unavailable"} or candidate.spot_state in {"occupied", "unavailable"} or candidate.reachable_state in {"unreachable", "blocked"}:
            raise ValueError("candidate_physical_state_invalid")
        previous = current
