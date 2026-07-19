"""结构化日程 DTO 到紧凑标签及受控 JSON 的单向 adapter。"""
from __future__ import annotations

import json


def render_candidates(candidates) -> str:
    """渲染完整候选，不使用字符级静默截断。"""
    return "\n".join(
        f'<candidate id="{item.candidate_id}" segment="{item.segment_id}" action="{item.action_id}" location="{item.location_id}" necessity="{item.necessity}" required_group="{item.required_group_id}" group="{item.primary_group}" />'
        for item in candidates
    )


def parse_selection(raw: str, candidates: dict[str, object]) -> dict[str, list[str]]:
    """解析工作/休息候选 ID 队列并做完全重复去重。"""
    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    payload = json.loads(cleaned.strip())
    if not isinstance(payload, dict):
        raise ValueError("day_plan_not_object")
    result: dict[str, list[str]] = {"work": [], "rest": []}
    seen: set[str] = set()
    for segment_id, field in (("work", "work_tasks"), ("rest", "rest_tasks")):
        values = payload.get(field)
        if not isinstance(values, list):
            raise ValueError("segment_queue_not_array")
        for value in values:
            candidate_id = str(value)
            if candidate_id not in candidates:
                raise ValueError("unknown_candidate")
            if candidate_id in seen:
                raise ValueError("duplicate_candidate")
            seen.add(candidate_id)
            result[segment_id].append(candidate_id)
    return result
