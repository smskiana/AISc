"""结构化日程 DTO 到紧凑标签及受控 JSON 的单向 adapter。"""
from __future__ import annotations

import json
import re


_TIME = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def render_candidates(candidates) -> str:
    """渲染完整候选，不使用字符级静默截断。"""
    return "\n".join(
        f'<candidate id="{item.candidate_id}" action="{item.action_id}" location="{item.location_id}" necessity="{item.necessity}" group="{item.primary_group}" start="{item.suggested_start_time}" />'
        for item in candidates
    )


def parse_selection(raw: str, candidates: dict[str, object]) -> list[tuple[str, str]]:
    """严格解析 candidate_id 与 HH:MM，并拒绝乱序和重复时间。"""
    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    payload = json.loads(cleaned.strip())
    if not isinstance(payload, list):
        raise ValueError("schedule_not_array")
    result: list[tuple[str, str]] = []
    seen_times: set[str] = set()
    previous = ""
    for item in payload:
        candidate_id = str(item.get("candidate_id") or "")
        start = str(item.get("planned_start_time") or "")
        if candidate_id not in candidates:
            raise ValueError("unknown_candidate")
        if not _TIME.fullmatch(start):
            raise ValueError("invalid_start_time")
        if start in seen_times or (previous and start <= previous):
            raise ValueError("non_monotonic_schedule")
        seen_times.add(start)
        previous = start
        result.append((candidate_id, start))
    minimum = min(6, len(candidates))
    if len(result) < minimum or len(result) > 10:
        raise ValueError("schedule_item_count_out_of_range")
    return result
