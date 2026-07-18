"""完全 LLM 路由模块：竞争候选逐跳选择，并提供可观测的本地降级。"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..prompting import PromptAssembler
from .deep_retrieval import DirectedDeepRetriever
from .retrieval_contracts import (
    DeepSearchRequest,
    DirectionResolution,
    FailureReason,
    LlmGraphSearchOutcome,
    LlmGraphSearchRequest,
    LocalSearchPolicy,
    SearchBudget,
    SearchPathEvidence,
    StopReason,
)

logger = logging.getLogger("sakurabashi.retrieval.llm_graph")


class LlmGraphRetriever:
    """将逐跳候选、LLM 选择预算和失败降级收拢为一个可测试 seam。"""

    def __init__(self, db, vector_store=None, prompt_assembler: PromptAssembler | None = None, llm=None):
        """注入图、向量、Prompt 和可替换 LLM。"""
        self.db = db
        self.vector_store = vector_store
        self.prompt_assembler = prompt_assembler or PromptAssembler()
        self.llm = llm
        self._local = DirectedDeepRetriever(db, vector_store)

    def search(self, request: LlmGraphSearchRequest) -> LlmGraphSearchOutcome:
        """逐跳执行 LLM 竞争选择，达到调用预算后明确停止。"""
        context = dict(request.route_context)
        direction = context.get("_direction")
        if direction is None:
            from .retrieval_direction import LocalDirectionProvider
            direction = LocalDirectionProvider().provide(context.get("_request"), context).direction
        local_policy = LocalSearchPolicy(SearchBudget(
            max_depth=request.policy.max_hops, beam_width=request.policy.selected_edges_per_hop,
            max_neighbors_per_node=request.policy.max_neighbors_per_node,
            max_expanded_edges=max(1, request.policy.max_hops * request.policy.max_frontier_nodes * request.policy.max_neighbors_per_node),
            max_anchor_count=0, max_answer_candidates=request.policy.max_frontier_nodes,
            min_path_score=0.0, early_stop_margin=0.0,
        ))
        frontier = list(request.start_node_ids)
        visited_nodes = set(frontier)
        visited_edges: set[str] = set()
        selected_edges: list[dict[str, Any]] = []
        path_evidence: list[SearchPathEvidence] = []
        candidate_edges_all: list[dict[str, Any]] = []
        calls = 0
        degraded = False
        counters = {"candidate_edges": 0, "candidate_chars": 0, "budget_rejections": 0}
        for hop in range(request.policy.max_hops):
            candidates = self._collect_candidates(request, direction, frontier, visited_nodes, visited_edges, local_policy)
            candidate_edges_all.extend(candidates)
            counters["candidate_edges"] += len(candidates)
            if not candidates:
                return self._outcome(selected_edges, path_evidence, candidate_edges_all, calls, degraded, counters, StopReason.FRONTIER_EXHAUSTED.value, FailureReason.NONE.value)
            candidates = candidates[: request.policy.max_candidate_edges]
            selected_limit = request.policy.selected_edges_per_hop
            if len(candidates) <= selected_limit:
                chosen = candidates
            else:
                if calls >= request.policy.max_llm_route_calls:
                    counters["budget_rejections"] += 1
                    return self._outcome(selected_edges, path_evidence, candidate_edges_all, calls, degraded, counters, StopReason.EDGE_BUDGET_EXHAUSTED.value, FailureReason.BUDGET_EXHAUSTED.value)
                calls += 1
                selected, error = self._select_with_llm(request, context, frontier, candidates, selected_limit, hop)
                if error:
                    degraded = True
                    chosen = candidates[:selected_limit]
                else:
                    chosen = selected
            for edge in chosen:
                edge_id = str(edge.get("edge_id", ""))
                node_id = str(edge.get("node_id", ""))
                visited_edges.add(edge_id)
                selected_edges.append(edge)
                path_evidence.append(SearchPathEvidence(
                    node_id=node_id, edge_id=edge_id, from_node_id=str(edge.get("from_node_id", "")),
                    direction=str(edge.get("direction", "ab")), score=float(edge.get("local_score", 0.0)),
                    score_components=edge.get("score_components", {}),
                ))
                if node_id not in visited_nodes:
                    visited_nodes.add(node_id)
            next_frontier = list(dict.fromkeys(str(edge.get("node_id")) for edge in chosen if edge.get("node_id") not in frontier))[:request.policy.max_frontier_nodes]
            if not next_frontier:
                break
            frontier = next_frontier
        failure = FailureReason.NONE.value if selected_edges else FailureReason.KNOWLEDGE_ABSENT.value
        return self._outcome(selected_edges, path_evidence, candidate_edges_all, calls, degraded, counters, StopReason.DEPTH_LIMIT_REACHED.value, failure)

    def _collect_candidates(self, request: LlmGraphSearchRequest, direction, frontier: list[str], visited_nodes: set[str], visited_edges: set[str], local_policy: LocalSearchPolicy) -> list[dict[str, Any]]:
        """收集稳定候选并只使用本地分数做预排序，不跳过竞争调用。"""
        node_map = {item.get("node_id"): item for item in self._local._get_nodes(request.npc_id, frontier)}
        batch_edges = self.db.get_directional_neighbors_batch(frontier, request.policy.max_neighbors_per_node) if hasattr(self.db, "get_directional_neighbors_batch") else {}
        candidates: list[dict[str, Any]] = []
        for from_id in frontier[: request.policy.max_frontier_nodes]:
            raw_edges = batch_edges.get(from_id) if batch_edges else self.db.get_directional_neighbors(from_id, limit=request.policy.max_neighbors_per_node)
            pending = [edge for edge in raw_edges if edge.get("id") not in visited_edges and edge.get("neighbor_id") not in visited_nodes and not edge.get("archived") and edge.get("allowed") is not False]
            neighbors = [str(edge.get("neighbor_id")) for edge in pending]
            nodes = {item.get("node_id"): item for item in self._local._get_nodes(request.npc_id, neighbors)}
            for edge in pending:
                node_id = str(edge.get("neighbor_id"))
                node = nodes.get(node_id, {"node_id": node_id, "type": "event", "value": "(记忆不可用)", "importance": 0.5})
                candidate = {
                    "edge_id": edge.get("id", ""), "node_id": node_id,
                    "clarity": float(edge.get("directional_clarity", 0.0) or 0.0),
                    "edge_type": edge.get("type", ""), "direction": edge.get("direction", "ab"),
                    "target_importance": float(edge.get("target_importance", 0.5) or 0.5),
                    "source_is_target": False, "from_node_id": from_id,
                    "from_type": node_map.get(from_id, {}).get("type", "unknown"),
                    "from_value": str(node_map.get(from_id, {}).get("value", from_id)),
                    "type": node.get("type", "event"), "value": str(node.get("value", "")),
                    "importance": float(node.get("importance", 0.5) or 0.5),
                }
                candidate["local_score"], candidate["score_components"] = self._local._score(candidate, DeepSearchRequest(
                    npc_id=request.npc_id, target_id=request.target_id, start_node_ids=request.start_node_ids,
                    target_start_id=None, direction=direction, policy=local_policy,
                ))
                candidates.append(candidate)
        return sorted(candidates, key=lambda item: (-float(item["local_score"]), str(item.get("edge_id", ""))))

    def _select_with_llm(self, request: LlmGraphSearchRequest, context: dict[str, Any], frontier: list[str], candidates: list[dict[str, Any]], selected_limit: int, hop: int) -> tuple[list[dict[str, Any]], str]:
        """构建字符受限 route Prompt 并解析选择下标。"""
        client = self.llm
        if client is None:
            from ..dialogue import llm_client as llm_module
            client = llm_module.llm_client
        if client is None or not getattr(client, "is_available", True):
            return [], "llm_unavailable"
        lines = []
        for index, edge in enumerate(candidates):
            summary = str(edge.get("value", ""))[: request.policy.candidate_summary_chars]
            lines.append(f"[{index}] {edge.get('edge_type', '?')}/{edge.get('direction', '?')} clarity={edge.get('clarity', 0.0):.2f} {summary}")
        candidate_text = "\n".join(lines)
        if len(candidate_text) > request.policy.max_route_prompt_chars:
            candidate_text = candidate_text[: request.policy.max_route_prompt_chars]
        prompt = self.prompt_assembler.build("memory_route", {
            "npc_id": request.npc_id, "target_name": context.get("target_name", request.target_id),
            "game_time": context.get("game_time", "未知"), "location": context.get("location", "street"),
            "emotion": context.get("emotion", "平静"), "energy": context.get("energy", 80),
            "current_need": context.get("current_need", "无"), "impression": context.get("impression", "暂无"),
            "participant_ids": ", ".join(context.get("participant_ids", [])),
            "query_text": context.get("query_text", "（无）"), "conversation_summary": context.get("conversation_summary", "（暂无）"),
            "conversation_turns": context.get("conversation_turns", "（暂无）"), "route_guidance": context.get("route_guidance", ""),
            "recent_memories": "\n".join(context.get("recent_memories", [])) or "（暂无）",
            "frontier_nodes": ", ".join(frontier), "candidates": candidate_text, "max_select": selected_limit,
        })
        try:
            payload = json.loads(self._strip_json_fence(client.chat(prompt, temperature=0.2)))
            selected = payload.get("selected", []) if isinstance(payload, dict) else []
            chosen = [candidates[index] for index in selected if isinstance(index, int) and 0 <= index < len(candidates)][:selected_limit]
            return (chosen or candidates[:selected_limit]), "" if chosen else "llm_empty"
        except Exception as error:
            logger.debug("memory_route failed: %s", error)
            return [], "llm_invalid"

    @staticmethod
    def _strip_json_fence(raw: str) -> str:
        """去掉 route JSON 的 markdown 包装。"""
        text = str(raw or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            return "\n".join(lines[1:-1]).strip() if len(lines) >= 2 else ""
        return text

    @staticmethod
    def _outcome(selected_edges, path_evidence, candidates, calls, degraded, counters, stop_reason, failure_reason):
        """统一构建 LLM route 输出 DTO。"""
        return LlmGraphSearchOutcome(
            node_ids=list(dict.fromkeys(str(edge.get("node_id")) for edge in selected_edges if edge.get("node_id"))),
            selected_edges=selected_edges, path_evidence=path_evidence,
            candidate_edges=candidates, stop_reason=stop_reason, failure_reason=failure_reason,
            llm_route_calls=calls, degraded_to_local=degraded, counters=counters,
        )
