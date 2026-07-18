"""带预算、beam 和路径证据的本地深层图检索。"""
from __future__ import annotations

import logging
from typing import Any

from .retrieval_contracts import (
    DeepSearchOutcome,
    DeepSearchRequest,
    FailureReason,
    SearchPathEvidence,
    StopReason,
)

logger = logging.getLogger("sakurabashi.retrieval.deep")


class DirectedDeepRetriever:
    """只负责固定起点之后的本地图扩张、评分和停止语义。"""

    def __init__(self, db, vector_store=None):
        """注入领域化图查询和节点内容读取依赖。"""
        self.db = db
        self.vector_store = vector_store

    def search(self, request: DeepSearchRequest) -> DeepSearchOutcome:
        """按 typed local policy 执行批量受限深搜。"""
        if not request.start_node_ids:
            return DeepSearchOutcome(failure_reason=FailureReason.START_NODES_NOT_FOUND.value)
        budget = request.policy.budget
        frontier = list(dict.fromkeys(request.start_node_ids))
        visited_nodes = set(frontier)
        visited_edges: set[str] = set()
        node_ids: list[str] = []
        selected_edges: list[dict[str, Any]] = []
        path_evidence: list[SearchPathEvidence] = []
        all_candidates: list[dict[str, Any]] = []
        layer_stats: list[dict[str, int]] = []
        counters = {"expanded_edges": 0, "filtered_archived": 0, "filtered_forbidden": 0, "filtered_loop": 0, "filtered_low_score": 0}
        stop_reason = StopReason.FRONTIER_EXHAUSTED.value
        best_score = 0.0
        anchor_ids = set(request.vector_anchor_ids[: budget.max_anchor_count])

        for depth in range(budget.max_depth):
            if counters["expanded_edges"] >= budget.max_expanded_edges:
                stop_reason = StopReason.EDGE_BUDGET_EXHAUSTED.value
                break
            candidates = self._collect_candidates(request, frontier, visited_nodes, visited_edges, counters)
            remaining_edges = max(0, budget.max_expanded_edges - counters["expanded_edges"])
            candidates = candidates[:remaining_edges]
            counters["expanded_edges"] += len(candidates)
            all_candidates.extend(candidates)
            layer_stats.append({
                "depth": depth + 1, "frontier_nodes": len(frontier),
                "neighbor_edges": len(candidates), "beam_nodes": 0,
                "candidate_edges": min(len(candidates), budget.max_answer_candidates),
            })
            if not candidates:
                stop_reason = StopReason.FRONTIER_EXHAUSTED.value
                break
            candidate_count_before_score_filter = len(candidates)
            candidates = [item for item in candidates if item["local_score"] >= budget.min_path_score or item["node_id"] in anchor_ids]
            counters["filtered_low_score"] += candidate_count_before_score_filter - len(candidates)
            if not candidates:
                stop_reason = StopReason.FRONTIER_EXHAUSTED.value
                break
            candidates.sort(key=lambda item: (-float(item["local_score"]), str(item.get("edge_id", "")), str(item.get("node_id", ""))))
            chosen = candidates[: budget.beam_width]
            next_frontier: list[str] = []
            for candidate in chosen:
                edge_id = str(candidate["edge_id"])
                node_id = str(candidate["node_id"])
                visited_edges.add(edge_id)
                selected_edges.append(candidate)
                evidence = SearchPathEvidence(
                    node_id=node_id, edge_id=edge_id, from_node_id=str(candidate["from_node_id"]),
                    direction=str(candidate.get("direction", "ab")), score=float(candidate["local_score"]),
                    score_components={key: float(value) for key, value in candidate.get("score_components", {}).items()},
                )
                path_evidence.append(evidence)
                if node_id not in visited_nodes:
                    visited_nodes.add(node_id)
                    node_ids.append(node_id)
                    next_frontier.append(node_id)
                best_score = max(best_score, float(candidate["local_score"]))
            layer_stats[-1]["beam_nodes"] = len(next_frontier)
            if not next_frontier:
                stop_reason = StopReason.FRONTIER_EXHAUSTED.value
                break
            if len(node_ids) >= budget.max_answer_candidates:
                stop_reason = StopReason.SUFFICIENT_EVIDENCE.value
                break
            if best_score >= 0.85 and depth > 0 and len(next_frontier) == 1:
                stop_reason = StopReason.EARLY_STOP_MARGIN_REACHED.value
                break
            frontier = next_frontier
        else:
            stop_reason = StopReason.DEPTH_LIMIT_REACHED.value

        if not node_ids:
            failure = FailureReason.NO_REACHABLE_PATH.value if request.direction.entity_mentions or request.vector_anchor_ids else FailureReason.KNOWLEDGE_ABSENT.value
        elif counters["expanded_edges"] >= budget.max_expanded_edges and frontier:
            failure = FailureReason.BUDGET_EXHAUSTED.value
        else:
            failure = FailureReason.NONE.value
        return DeepSearchOutcome(
            node_ids=node_ids[: budget.max_answer_candidates], selected_edges=selected_edges,
            path_evidence=path_evidence, candidate_edges=all_candidates[: budget.max_answer_candidates],
            stop_reason=stop_reason, failure_reason=failure, layer_stats=layer_stats, counters=counters,
        )

    def _collect_candidates(self, request: DeepSearchRequest, frontier: list[str], visited_nodes: set[str], visited_edges: set[str], counters: dict[str, int]) -> list[dict[str, Any]]:
        """按前沿批量收集候选，并在评分前完成 archived / 权限 / 环路过滤。"""
        node_map = {item.get("node_id"): item for item in self._get_nodes(request.npc_id, frontier)}
        batch_edges = self.db.get_directional_neighbors_batch(frontier, request.policy.budget.max_neighbors_per_node) if hasattr(self.db, "get_directional_neighbors_batch") else {}
        candidates: list[dict[str, Any]] = []
        for from_node_id in frontier:
            if counters["expanded_edges"] >= request.policy.budget.max_expanded_edges:
                break
            edges = batch_edges.get(from_node_id) if batch_edges else self.db.get_directional_neighbors(from_node_id, limit=request.policy.budget.max_neighbors_per_node)
            neighbor_ids: list[str] = []
            pending: list[dict[str, Any]] = []
            for edge in edges:
                if edge.get("id") in visited_edges or edge.get("neighbor_id") in visited_nodes:
                    counters["filtered_loop"] += 1
                    continue
                if edge.get("archived") or edge.get("allowed") is False:
                    counters["filtered_forbidden"] += 1 if edge.get("allowed") is False else 0
                    counters["filtered_archived"] += 1 if edge.get("archived") else 0
                    continue
                pending.append(edge)
                neighbor_ids.append(str(edge.get("neighbor_id")))
            neighbor_map = {item.get("node_id"): item for item in self._get_nodes(request.npc_id, neighbor_ids)}
            from_node = node_map.get(from_node_id, {"node_id": from_node_id, "type": "unknown", "value": str(from_node_id)})
            for edge in pending:
                neighbor_id = str(edge.get("neighbor_id"))
                node = neighbor_map.get(neighbor_id, {"node_id": neighbor_id, "type": "event", "value": "(记忆不可用)", "importance": 0.5})
                if node.get("archived") or node.get("allowed") is False:
                    counters["filtered_archived"] += 1 if node.get("archived") else 0
                    counters["filtered_forbidden"] += 1 if node.get("allowed") is False else 0
                    continue
                candidate = {
                    "edge_id": edge.get("id", ""), "node_id": neighbor_id,
                    "clarity": float(edge.get("directional_clarity", 0.0) or 0.0),
                    "edge_type": edge.get("type", ""), "direction": edge.get("direction", "ab"),
                    "target_importance": float(edge.get("target_importance", 0.5) or 0.5),
                    "source_is_target": bool(request.target_start_id and from_node_id == request.target_start_id),
                    "from_node_id": from_node_id, "from_type": from_node.get("type", "unknown"),
                    "from_value": str(from_node.get("value", from_node_id)),
                    "type": node.get("type", "event"), "value": str(node.get("value", "")),
                    "importance": float(node.get("importance", 0.5) or 0.5),
                }
                candidate["local_score"], candidate["score_components"] = self._score(candidate, request)
                candidates.append(candidate)
        unique: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            existing = unique.get(str(candidate["edge_id"]))
            if existing is None or candidate["local_score"] > existing["local_score"]:
                unique[str(candidate["edge_id"])] = candidate
        return sorted(unique.values(), key=lambda item: (-float(item["local_score"]), str(item["edge_id"])))

    def _score(self, candidate: dict[str, Any], request: DeepSearchRequest) -> tuple[float, dict[str, float]]:
        """用受控映射表组合方向、实体、关系和图证据分。"""
        direction = request.direction
        value = str(candidate.get("value", ""))
        edge_type = str(candidate.get("edge_type", ""))
        entity_hit = 1.0 if any(mention and mention in value for mention in direction.entity_mentions) else 0.0
        location_hit = 1.0 if any(mention and mention in value for mention in direction.location_mentions) else 0.0
        facet_map = {"relationship": "affinity", "involved": "shared_event", "mentioned": "knowledge_source", "felt": "impression_basis"}
        facet_hit = 1.0 if facet_map.get(edge_type) in direction.relation_facets else 0.0
        theme_map = {"person": {"identity", "relationship"}, "event": {"past_event", "recent_activity", "cause"}, "reflection": {"relationship", "cause", "emotion"}, "emotion": {"emotion"}, "place": {"current_location"}}
        direction_hit = 1.0 if theme_map.get(str(candidate.get("type", "")), set()) & set(direction.themes) else 0.0
        if location_hit:
            direction_hit = max(direction_hit, 1.0)
        source_reliability = 0.9 if edge_type in {"involved", "relationship", "happened_at", "located_at"} else 0.65
        novel = 1.0 if candidate.get("node_id") not in request.start_node_ids else 0.0
        depth_penalty = 0.0
        if direction.recall_intent == "locate_person" and candidate.get("type") == "place":
            direction_hit = 1.0
        components = {
            "direction_relevance": direction_hit, "entity_alignment": entity_hit,
            "relation_facet_alignment": facet_hit, "edge_clarity": max(0.0, min(1.0, float(candidate.get("clarity", 0.0)))),
            "time_alignment": 0.75 if direction.time_scope in {"recent", "any"} else 0.55,
            "source_reliability": source_reliability, "target_context": 1.0 if candidate.get("source_is_target") else 0.45,
            "node_importance": max(0.0, min(1.0, float(candidate.get("importance", 0.5)))), "novel_evidence": novel,
            "depth_penalty_per_extra_hop": depth_penalty, "repeated_topic_penalty": 0.0, "uncertainty_penalty": 0.0,
        }
        weights = request.policy.budget
        score = (
            0.24 * components["direction_relevance"] + 0.18 * components["entity_alignment"]
            + 0.12 * components["relation_facet_alignment"] + 0.10 * components["edge_clarity"]
            + 0.08 * components["time_alignment"] + 0.08 * components["source_reliability"]
            + 0.06 * components["target_context"] + 0.06 * components["node_importance"]
            + 0.08 * components["novel_evidence"] + float(candidate.get("importance", 0.5)) * 0.20
        )
        if candidate.get("source_is_target"):
            score += 0.08
        return round(score, 6), components

    def _get_nodes(self, npc_id: str, node_ids: list[str]) -> list[dict[str, Any]]:
        """批量读取节点内容，保留无向量层时的安全占位。"""
        if not node_ids:
            return []
        if self.vector_store and hasattr(self.vector_store, "get_batch"):
            return list(self.vector_store.get_batch(npc_id, node_ids) or [])
        return [{"node_id": node_id, "type": "event", "value": "(记忆不可用)", "importance": 0.5} for node_id in node_ids]
