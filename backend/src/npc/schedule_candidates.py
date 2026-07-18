"""结构化日程候选、硬过滤、评分与确定性 fallback。"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class ScheduleCandidate:
    """表示 LLM 只能引用的单个合法计划候选。"""

    candidate_id: str
    action_id: str
    location_id: str
    necessity: str
    primary_group: str
    groups: tuple[str, ...]
    relevance: float
    suggested_start_time: str
    target_person_id: str = ""
    evidence_ids: tuple[str, ...] = ()
    rejection_reason: str = ""


class ScheduleCandidateBuilder:
    """从 affordance 和 routine 建立覆盖多个语义组的候选集合。"""

    def __init__(self, catalog):
        self._catalog = catalog

    def build(self, npc_id: str, routines: list[tuple[int, int, str, str]], physical_state: dict | None = None) -> list[ScheduleCandidate]:
        """构建并过滤候选；unknown 物理状态只降权，不伪造可用。"""
        physical_state = physical_state or {}
        candidates: list[ScheduleCandidate] = []
        routine_keys = {(action, location): (hour, minute) for hour, minute, action, location in routines}
        for action_id in sorted(self._catalog.action_ids):
            for location_id in self._catalog.allowed_locations(npc_id, action_id):
                hour, minute = routine_keys.get((action_id, location_id), (17 if action_id == "visit" else 13, 0))
                group = self._group(action_id, (action_id, location_id) in routine_keys)
                necessity = "required" if action_id in {"eat", "sleep"} or action_id in {"work_open", "work_close"} else ("important" if group in {"occupation", "routine", "need"} else "optional")
                state = str((physical_state.get("locations") or {}).get(location_id, "unknown"))
                if state in {"closed", "unavailable"}:
                    continue
                relevance = 1.0 if necessity == "required" else (0.75 if necessity == "important" else 0.45)
                if state == "unknown":
                    relevance -= 0.05
                stable = hashlib.sha256(f"{npc_id}|{action_id}|{location_id}".encode()).hexdigest()[:16]
                candidates.append(ScheduleCandidate(stable, action_id, location_id, necessity, group, (group,), relevance, f"{hour:02d}:{minute:02d}"))
        return candidates

    @staticmethod
    def _group(action_id: str, is_routine: bool) -> str:
        """把可扩展 action 集合归入稳定计划组。"""
        if is_routine:
            return "routine"
        if action_id.startswith("work_") or action_id == "patrol":
            return "occupation"
        if action_id in {"eat", "rest", "sleep"}:
            return "need"
        if action_id in {"visit", "talk", "greet", "give_item"}:
            return "relationship"
        return "exploration"


def deterministic_fallback(candidates: list[ScheduleCandidate], game_day: int, npc_id: str, attempt: int = 0, target_count: int = 8) -> tuple[list[ScheduleCandidate], int]:
    """按必须度和稳定加权随机生成可复现 fallback。"""
    seed = int.from_bytes(hashlib.sha256(f"{game_day}|{npc_id}|{attempt}".encode()).digest()[:8], "big")
    rng = random.Random(seed)
    rank = {"required": 0, "important": 1, "optional": 2}
    decorated = [(rank[item.necessity], -item.relevance, rng.random(), item) for item in candidates]
    decorated.sort(key=lambda value: value[:3])
    selected = [item for _, _, _, item in decorated[:target_count]]
    selected.sort(key=lambda item: item.suggested_start_time)
    return selected, seed

