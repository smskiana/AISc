"""日程选择的最终硬约束校验。"""
from __future__ import annotations


def validate_selection(selected, candidates) -> None:
    """验证双队列归属、分段、必要项和物理合法性。"""
    by_id = {item.candidate_id: item for item in candidates}
    if not selected:
        raise ValueError("empty_schedule")
    ids = list(selected.get("work", ())) + list(selected.get("rest", ()))
    minimum = min(2, len(candidates))
    if not minimum <= len(ids) <= 10:
        raise ValueError("schedule_item_count_out_of_range")
    if len(ids) != len(set(ids)) or any(candidate_id not in by_id for candidate_id in ids):
        raise ValueError("candidate_ownership_invalid")
    required_groups = {item.required_group_id for item in candidates if item.required_group_id}
    if len(required_groups) > 10:
        raise ValueError("required_group_count_out_of_range")
    selected_required_groups = {by_id[candidate_id].required_group_id for candidate_id in ids if by_id[candidate_id].required_group_id}
    if not required_groups.issubset(selected_required_groups):
        raise ValueError("required_group_missing")
    for segment_id in ("work", "rest"):
        for candidate_id in selected.get(segment_id, ()):
            if by_id[candidate_id].segment_id != segment_id:
                raise ValueError("candidate_segment_mismatch")
    for candidate_id in ids:
        candidate = by_id[candidate_id]
        if candidate.business_state in {"closed", "unavailable"} or candidate.spot_state in {"occupied", "unavailable"} or candidate.reachable_state in {"unreachable", "blocked"}:
            raise ValueError("candidate_physical_state_invalid")
        if candidate.lifecycle_action:
            raise ValueError("lifecycle_action_not_queueable")
