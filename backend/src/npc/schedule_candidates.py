"""结构化日程候选、世界硬过滤、评分与确定性 fallback。"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class ScheduleCandidate:
    """表示 LLM 只能引用的一条已验证 action-location-role 候选。"""

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
    role: str = "self"
    legal_start_minute: int = 0
    legal_end_minute: int = 1439
    weather: tuple[str, ...] = ()
    business_state: str = "unknown"
    spot_state: str = "unknown"
    reachable_state: str = "unknown"
    position_cost: float = 0.0
    source_reason: str = "affordance"
    relevance_components: dict[str, float] = field(default_factory=dict)
    evidence_similarity: float = 0.0
    graph_path_score: float = 0.0
    retrieval_trace_ids: tuple[str, ...] = ()


class ScheduleCandidateBuilder:
    """从 affordance、routine 和 Unity 世界快照建立合法候选。"""

    def __init__(self, catalog):
        self._catalog = catalog

    def build(self, npc_id: str, routines: list[tuple[int, int, str, str]], physical_state: dict | None = None) -> tuple[list[ScheduleCandidate], dict[str, int]]:
        """构建候选并在 Prompt 前确定性排除不可执行项。"""
        physical_state = physical_state or {}
        candidates: list[ScheduleCandidate] = []
        rejections: dict[str, int] = {}
        routine_keys = {(action, location): (hour, minute) for hour, minute, action, location in routines}
        for action_id in sorted(self._catalog.action_ids):
            for location_id in self._catalog.allowed_locations(npc_id, action_id):
                candidate, reason = self._candidate(npc_id, action_id, location_id, routine_keys, physical_state)
                if candidate is None:
                    rejections[reason] = rejections.get(reason, 0) + 1
                else:
                    candidates.append(candidate)
        return self._ensure_group_seats(candidates), rejections

    def _candidate(self, npc_id, action_id, location_id, routine_keys, physical_state):
        """投影一个候选的物理约束与可解释相关度。"""
        hour, minute = routine_keys.get((action_id, location_id), (17 if action_id == "visit" else 13, 0))
        group = self._group(action_id, (action_id, location_id) in routine_keys)
        necessity = "required" if action_id in {"eat", "sleep", "work_open", "work_close"} else ("important" if group in {"occupation", "routine", "need"} else "optional")
        location = (physical_state.get("locations") or {}).get(location_id, {})
        if not isinstance(location, dict):
            location = {"open_state": str(location)}
        business = str(location.get("open_state", "unknown"))
        reachable = str(location.get("reachable_state", "unknown"))
        spot = (physical_state.get("spots") or {}).get(location.get("spot_id") or location_id, {})
        if not isinstance(spot, dict):
            spot = {"availability": str(spot)}
        spot_state = str(spot.get("availability", "unknown"))
        if business in {"closed", "unavailable"}:
            return None, "business_closed"
        if reachable in {"unreachable", "blocked"}:
            return None, "travel_time_exceeded"
        if spot_state in {"unavailable", "occupied"}:
            return None, "spot_unavailable"
        weather = str(physical_state.get("weather") or "unknown")
        allowed_weather = tuple(location.get("allowed_weather") or ())
        if allowed_weather and weather not in allowed_weather and weather != "unknown":
            return None, "weather_forbidden"
        if weather in {"rain", "rainy", "storm"} and (location.get("outdoor") or "park" in location_id or "river" in location_id):
            return None, "weather_forbidden"
        position_cost = float(location.get("position_cost", location.get("travel_cost", 0.0)) or 0.0)
        base = 1.0 if necessity == "required" else (0.75 if necessity == "important" else 0.45)
        components = {"necessity": base, "position_cost": -position_cost}
        if business == "unknown" or reachable == "unknown" or spot_state == "unknown":
            components["unknown_world_state"] = -0.05
        if weather in {"rain", "rainy"} and not (location.get("outdoor") or "park" in location_id):
            components["weather"] = 0.05
        stable = hashlib.sha256(f"{npc_id}|{action_id}|{location_id}".encode()).hexdigest()[:16]
        return ScheduleCandidate(stable, action_id, location_id, necessity, group, (group,), sum(components.values()), f"{hour:02d}:{minute:02d}", role="worker" if group == "occupation" else "self", legal_start_minute=int(location.get("open_minute", 0) or 0), legal_end_minute=int(location.get("close_minute", 1439) or 1439), weather=allowed_weather, business_state=business, spot_state=spot_state, reachable_state=reachable, position_cost=position_cost, source_reason="routine" if (action_id, location_id) in routine_keys else "affordance", relevance_components=components), ""

    @staticmethod
    def _ensure_group_seats(candidates: list[ScheduleCandidate]) -> list[ScheduleCandidate]:
        """保持基础组席位；记忆层不得删除这些本地合法候选。"""
        return sorted(candidates, key=lambda item: (item.necessity != "required", item.primary_group, item.suggested_start_time, item.candidate_id))

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


def apply_memory_scores(candidates: list[ScheduleCandidate], evidence_by_group: dict[str, dict]) -> list[ScheduleCandidate]:
    """把批量检索证据写回候选，且不因缺证据删除基础组。"""
    enhanced = []
    for item in candidates:
        evidence = evidence_by_group.get(item.primary_group, {})
        similarity, graph_score = float(evidence.get("similarity", 0.0)), float(evidence.get("graph_path_score", 0.0))
        adjustment = similarity + graph_score
        if not evidence and item.primary_group in {"relationship", "exploration"}:
            adjustment = -0.08
        components = {**item.relevance_components, "memory_similarity": similarity, "graph_path": graph_score}
        enhanced.append(replace(item, relevance=item.relevance + adjustment, evidence_ids=tuple(evidence.get("evidence_ids", ())), evidence_similarity=similarity, graph_path_score=graph_score, retrieval_trace_ids=tuple(evidence.get("trace_ids", ())), relevance_components=components))
    return enhanced


def deterministic_fallback(candidates: list[ScheduleCandidate], game_day: int, npc_id: str, attempt: int = 0, target_count: int = 8) -> tuple[list[ScheduleCandidate], int, dict[str, str]]:
    """按必须度、相关度和稳定种子生成可复现 fallback 及淘汰原因。"""
    seed = int.from_bytes(hashlib.sha256(f"{game_day}|{npc_id}|{attempt}".encode()).digest()[:8], "big")
    rng = random.Random(seed)
    rank = {"required": 0, "important": 1, "optional": 2}
    decorated = [(rank[item.necessity], -item.relevance, rng.random(), item) for item in candidates]
    decorated.sort(key=lambda value: value[:3])
    selected = [item for _, _, _, item in decorated[:target_count]]
    reasons = {item.candidate_id: ("selected_required" if item.necessity == "required" else "selected_ranked") for item in selected}
    reasons.update({item.candidate_id: "omitted_target_limit" for _, _, _, item in decorated[target_count:]})
    selected.sort(key=lambda item: item.suggested_start_time)
    return selected, seed, reasons
