"""图记忆检索 facade：策略选择、结果重建和兼容入口。"""
from __future__ import annotations

import logging
import os
import time
import uuid
from copy import deepcopy
from dataclasses import replace
from typing import Any

from ..database.sqlite_client import SQLiteClient
from ..dialogue.player_name import get_player_display_name, get_player_name_candidates, render_player_tokens
from ..prompting import PromptAssembler
from .deep_retrieval import DirectedDeepRetriever
from .llm_graph_retrieval import LlmGraphRetriever
from .retrieval_contracts import (
    DeepSearchRequest,
    DirectionResolution,
    FailureReason,
    LlmGraphSearchRequest,
    RetrievalModePolicy,
    RetrievalRequest,
    RetrievalResult,
    RetrievalStrategy,
    RetrievalTrace,
    VectorSearchHit,
)
from .retrieval_context import RetrievalContextAssembler
from .retrieval_diagnostics import RetrievalTraceStore, retrieval_trace_store
from .retrieval_direction import DirectionResolver, LocalDirectionProvider, LlmDirectionProvider, NPC_NAMES
from .retrieval_policy import RetrievalPolicyRegistry
from .retrieval_query import RetrievalQueryPlanner

logger = logging.getLogger("sakurabashi.retrieval")

PLAYER_RETRIEVAL_BASE_HINTS = ("喫茶店", "奶奶", "从城市回来", "樱桥通")

# 旧测试和少量外部脚本仍读取这个兼容观察面；新的运行时 policy 来自 YAML。
RETRIEVAL_MODE_CONFIGS = {
    "player_dialogue": {"max_edges_per_hop": 12, "edges_per_route": 8, "max_hops": 4, "short_term_limit": 4, "short_term_days": 3, "min_graph_nodes": 1, "vector_fallback_limit": 2, "vector_search_top_k": 8, "final_memory_limit": 5, "local_route_min_score": 0.25, "local_route_margin": 0.18},
    "npc_dialogue": {"max_edges_per_hop": 8, "edges_per_route": 4, "max_hops": 2, "short_term_limit": 2, "short_term_days": 2, "min_graph_nodes": 1, "vector_fallback_limit": 1, "vector_search_top_k": 4, "final_memory_limit": 3, "local_route_min_score": 0.30, "local_route_margin": 0.22},
    "nightly_impression": {"max_edges_per_hop": 20, "edges_per_route": 12, "max_hops": 6, "short_term_limit": 10, "short_term_days": 7, "min_graph_nodes": 1, "vector_fallback_limit": 3, "vector_search_top_k": 12, "final_memory_limit": 6, "local_route_min_score": 0.18, "local_route_margin": 0.12},
}
LEGACY_BASE_CONFIGS = deepcopy(RETRIEVAL_MODE_CONFIGS)


def _memory_trace_enabled() -> bool:
    """读取是否开启文本日志诊断。"""
    return os.getenv("SAKURA_MEMORY_TRACE", "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_day(time_str: str) -> int:
    """从“第X天 HH:MM”或“Day X”里取出 X。"""
    digits: list[str] = []
    for char in str(time_str or ""):
        if char.isdigit():
            digits.append(char)
        elif digits:
            break
    return int("".join(digits)) if digits else 999


def _turn_text(turn: Any) -> str:
    """提取近期对白文本。"""
    return str(turn.get("text", "")) if isinstance(turn, dict) else str(getattr(turn, "text", turn))


def _target_name(target_id: str) -> str:
    """返回稳定目标显示名。"""
    return get_player_display_name() if target_id == "player" else NPC_NAMES.get(target_id, target_id)


def _player_retrieval_hints() -> tuple[str, ...]:
    """按当前玩家昵称生成检索关键词。"""
    return get_player_name_candidates() + PLAYER_RETRIEVAL_BASE_HINTS


class RetrievalEngine:
    """稳定 facade：兼容入口、策略选择、结果重建和统一诊断。"""

    def __init__(self, db: SQLiteClient, lancedb=None, clarity_recover=None, policy_registry: RetrievalPolicyRegistry | None = None, trace_store: RetrievalTraceStore | None = None, llm=None):
        """注入存储和可替换策略依赖。"""
        self.db = db
        self.lancedb = lancedb
        self._clarity_recover = clarity_recover
        self.policy_registry = policy_registry or RetrievalPolicyRegistry()
        self.trace_store = trace_store or retrieval_trace_store
        self.prompt_assembler = PromptAssembler()
        self.direction_resolver = DirectionResolver(self.prompt_assembler)
        self.query_planner = RetrievalQueryPlanner()
        self.context_assembler = RetrievalContextAssembler()
        self.deep_retriever = DirectedDeepRetriever(db, lancedb)
        self.llm_retriever = LlmGraphRetriever(db, lancedb, self.prompt_assembler, llm=llm)

    def set_clarity_recover(self, clarity_recover) -> None:
        """注入边清晰度恢复回调。"""
        self._clarity_recover = clarity_recover

    def retrieve(self, request_or_npc_id: RetrievalRequest | str, target_id: str = "player", location: str = "", game_time: str = "", mode: str | None = None) -> RetrievalResult | str:
        """执行结构化检索，并保留旧位置参数的字符串返回入口。"""
        structured = isinstance(request_or_npc_id, RetrievalRequest)
        request = request_or_npc_id if structured else RetrievalRequest(
            npc_id=str(request_or_npc_id), conversation_participant_ids=[target_id] if target_id else [],
            location_id=location, game_time=game_time, mode=mode or ("player_dialogue" if target_id == "player" else "npc_dialogue"),
        )
        result = self._retrieve_result(request)
        return result if structured else result.rebuilt_context

    def probe(self, request: RetrievalRequest) -> RetrievalResult:
        """执行编辑器只读检索探针，不恢复 clarity 或写持久检索日志。"""
        return self._retrieve_result(request, side_effects_disabled=True)

    def _retrieve_result(self, request: RetrievalRequest, side_effects_disabled: bool = False) -> RetrievalResult:
        """按 policy 完成方向、图搜索、向量复用、重建和 trace。"""
        started = time.perf_counter()
        target_id = request.conversation_participant_ids[0] if request.conversation_participant_ids else "player"
        mode = request.mode or ("player_dialogue" if target_id == "player" else "npc_dialogue")
        policy = self._effective_policy(mode)
        start_ids, target_start_id = self._find_start_nodes(request.npc_id, target_id)
        trace_id = f"retrieval_{uuid.uuid4().hex[:12]}"
        if not start_ids:
            trace = RetrievalTrace(trace_id, request.npc_id, target_id, mode, policy.strategy.value, policy.version, failure_reason=FailureReason.START_NODES_NOT_FOUND.value)
            self.trace_store.add(trace)
            return RetrievalResult(diagnostics={"retrieval_trace_id": trace_id, "failure_reason": FailureReason.START_NODES_NOT_FOUND.value})
        route_context = self._build_route_context(request.npc_id, target_id, request.location_id, request.game_time, policy, mode, request)
        direction_resolution = None
        if request.direction_override is not None:
            direction_resolution = DirectionResolution(
                direction=request.direction_override,
                source=request.direction_source or "request_override",
            )
            direction_context = self.direction_resolver.build_context(request, policy.context, route_context.get("recent_memories", []))
            route_context["_context_budget"] = direction_context.get("_context_budget", {})
            route_context["_direction"] = direction_resolution.direction
        elif policy.strategy != RetrievalStrategy.LLM_FULL_ROUTE:
            provider = LocalDirectionProvider() if policy.strategy == RetrievalStrategy.LOCAL_ONLY else LlmDirectionProvider(self.prompt_assembler, LocalDirectionProvider(), self.llm_retriever.llm)
            direction_context = self.direction_resolver.build_context(request, policy.context, route_context.get("recent_memories", []))
            route_context["_context_budget"] = direction_context.get("_context_budget", {})
            direction_resolution = self.direction_resolver.resolve(request, direction_context, provider)
            route_context["_direction"] = direction_resolution.direction
        else:
            direction_context = self.direction_resolver.build_context(request, policy.context, route_context.get("recent_memories", []))
            route_context["_context_budget"] = direction_context.get("_context_budget", {})
            direction_resolution = self.direction_resolver.resolve(request, direction_context, LocalDirectionProvider())
            direction_resolution = replace(direction_resolution, source="not_applicable")
            route_context["_direction"] = direction_resolution.direction
        query_plan = self.query_planner.plan(request, direction_resolution, policy)
        vector_hits, vector_query = (self._vector_search_once(request.npc_id, query_plan.embedding_query, policy) if policy.strategy != RetrievalStrategy.LLM_FULL_ROUTE else ([], query_plan.embedding_query))
        vector_anchor_ids = [hit.node_id for hit in vector_hits]
        if policy.strategy == RetrievalStrategy.LLM_FULL_ROUTE:
            outcome = self.llm_retriever.search(LlmGraphSearchRequest(request.npc_id, target_id, start_ids, {**route_context, "_request": request}, policy.llm_route, side_effects_disabled))
            selected_edges, node_ids, candidates = outcome.selected_edges, outcome.node_ids, outcome.candidate_edges
            stop_reason, failure_reason, degraded = outcome.stop_reason, outcome.failure_reason, outcome.degraded_to_local
            layer_stats, counters = [], outcome.counters
            llm_route_calls = outcome.llm_route_calls
        else:
            outcome = self.deep_retriever.search(DeepSearchRequest(request.npc_id, target_id, start_ids, target_start_id, direction_resolution.direction, policy.local_search, vector_anchor_ids, side_effects_disabled))
            selected_edges, node_ids, candidates = outcome.selected_edges, outcome.node_ids, outcome.candidate_edges
            stop_reason, failure_reason, degraded = outcome.stop_reason, outcome.failure_reason, direction_resolution.source.startswith("llm_")
            layer_stats, counters = outcome.layer_stats, outcome.counters
            llm_route_calls = 0 if policy.strategy == RetrievalStrategy.LOCAL_ONLY else 1 if direction_resolution.source == "llm" else 0
        graph_node_count = len(node_ids)
        fallback_ids: list[str] = []
        if len(node_ids) < max(1, policy.context.final_memory_limit // 3):
            fallback_ids = [node_id for node_id in vector_anchor_ids if node_id not in node_ids][: policy.context.vector_fallback_limit]
            node_ids.extend(fallback_ids)
        node_rows = self._get_node_data(request.npc_id, node_ids)
        graph_scores = {str(item.get("node_id")): item for item in candidates}
        ranked_candidates = [{**node, **({"local_score": graph_scores[str(node.get("node_id"))].get("local_score", 0.0)} if str(node.get("node_id")) in graph_scores else {})} for node in node_rows]
        assembly = self.context_assembler.assemble(ranked_candidates, query_plan, vector_hits, request.game_time, policy)
        nodes = [node for entry in assembly.entries for node in node_rows if str(node.get("node_id")) == entry.node_id]
        if not side_effects_disabled:
            self._recover_selected_edges(selected_edges)
        rebuilt = assembly.context_text
        elapsed = time.perf_counter() - started
        if assembly.failure_reason != FailureReason.NONE.value:
            failure_reason = assembly.failure_reason
        elif not node_ids and failure_reason == FailureReason.NONE.value:
            failure_reason = FailureReason.KNOWLEDGE_ABSENT.value
        trace = self._build_trace(trace_id, request, mode, policy, direction_resolution, start_ids, vector_hits, selected_edges, assembly, query_plan, vector_query, layer_stats, counters, candidates, stop_reason, failure_reason, degraded, elapsed, fallback_ids, route_context.get("_context_budget", {}))
        trace.vector_query_count = 1 if policy.strategy != RetrievalStrategy.LLM_FULL_ROUTE and self.lancedb and hasattr(self.lancedb, "search") else 0
        self.trace_store.add(trace)
        diagnostics = {**trace.diagnostics, "retrieval_trace_id": trace_id, "direction_source": trace.direction_source, "strategy": trace.strategy, "direction": trace.direction, "mentions": trace.mentions, "target_anchors": trace.target_anchors, "layer_stats": trace.layer_stats, "path_evidence": trace.path_evidence, "vector_hit_usage": trace.vector_hit_usage, "policy_summary": trace.policy_summary, "stop_reason": stop_reason, "failure_reason": failure_reason, "degraded_to_local": degraded, "llm_direction_calls": 1 if direction_resolution and direction_resolution.source == "llm" else 0, "llm_route_calls": llm_route_calls, "vector_query_count": trace.vector_query_count}
        if not side_effects_disabled:
            self._write_retrieval_log(request.npc_id, target_id, mode, request.game_time, request.location_id, graph_node_count, len(fallback_ids), nodes, selected_edges, diagnostics, elapsed)
        return RetrievalResult(rebuilt_context=rebuilt, start_node_ids=start_ids, selected_edge_ids=[str(item.get("edge_id")) for item in selected_edges if item.get("edge_id")], retrieved_node_ids=[entry.node_id for entry in assembly.entries], vector_query_preview=vector_query, fallback_used=bool(fallback_ids), diagnostics=diagnostics)

    def _effective_policy(self, mode: str) -> RetrievalModePolicy:
        """读取已校验 policy，并只为旧测试私有 seam映射兼容数值。"""
        policy = self.policy_registry.get(mode)
        legacy = RETRIEVAL_MODE_CONFIGS.get(mode)
        baseline = LEGACY_BASE_CONFIGS.get(mode)
        if not legacy or legacy == baseline:
            return policy
        budget = policy.local_search.budget
        budget = replace(
            budget,
            max_depth=int(legacy.get("max_hops", budget.max_depth)),
            beam_width=max(1, int(legacy.get("edges_per_route", budget.beam_width))),
            max_neighbors_per_node=int(legacy.get("max_edges_per_hop", budget.max_neighbors_per_node)),
            min_path_score=max(0.0, min(1.0, float(legacy.get("local_route_min_score", budget.min_path_score)))),
            early_stop_margin=max(0.0, min(1.0, float(legacy.get("local_route_margin", budget.early_stop_margin)))),
        )
        context = replace(policy.context, vector_fallback_limit=int(legacy.get("vector_fallback_limit", policy.context.vector_fallback_limit)), vector_search_top_k=int(legacy.get("vector_search_top_k", policy.context.vector_search_top_k)), final_memory_limit=int(legacy.get("final_memory_limit", policy.context.final_memory_limit)), recent_memory_limit=int(legacy.get("short_term_limit", policy.context.recent_memory_limit)))
        return replace(policy, local_search=replace(policy.local_search, budget=budget), context=context)

    def _build_route_context(self, npc_id: str, target_id: str, location: str, game_time: str, config: RetrievalModePolicy | dict[str, Any], mode: str, request: RetrievalRequest | None = None) -> dict[str, Any]:
        """整理方向和 route Prompt 需要的结构化上下文。"""
        limits = config.context if isinstance(config, RetrievalModePolicy) else config
        state = self.db.fetchone("SELECT emotion, energy, current_need FROM npc_states WHERE npc_id=?", (npc_id,)) or {}
        day_window = int(limits.get("short_term_days", 7)) if isinstance(limits, dict) else 7
        memory_limit = int(limits.get("short_term_limit", 4)) if isinstance(limits, dict) else int(config.context.recent_memory_limit)
        recent = self._get_recent_memory_summaries(npc_id, game_time, day_window, memory_limit)
        return {"npc_id": npc_id, "target_id": target_id, "target_name": _target_name(target_id), "location": location or "street", "game_time": game_time or "", "emotion": state.get("emotion", "平静"), "energy": state.get("energy", 80), "current_need": state.get("current_need") or "无", "impression": self._get_impression_context(npc_id, target_id), "recent_memories": recent, "mode": mode, "query_text": request.query_text if request else "", "conversation_summary": request.conversation_summary if request else "", "recent_turns": list(request.recent_turns) if request else [], "participant_ids": list(request.conversation_participant_ids) if request else [target_id]}

    def _get_recent_memory_summaries(self, npc_id: str, game_time: str, day_window: int, limit: int) -> list[str]:
        """取近期短期记忆摘要。"""
        rows = self.db.fetchall("SELECT content, created_at_game_time FROM short_term_memories WHERE subject_id = ? ORDER BY created_at_game_time DESC LIMIT 32", (npc_id,))
        current_day = _parse_day(game_time)
        return [self._summarize_memory_text(row.get("content", "")) for row in rows if row.get("content") and current_day - _parse_day(row.get("created_at_game_time", "")) < day_window][:limit]

    @staticmethod
    def _summarize_memory_text(content: str, max_len: int = 48) -> str:
        """把短期记忆压成单行。"""
        text = " ".join(line.strip() for line in str(content).splitlines() if line.strip())
        return text[:max_len]

    def _find_start_nodes(self, npc_id: str, target_id: str) -> tuple[list[str], str | None]:
        """只返回当前 NPC 的 self 和当前对话对象 person 两个固定起点。"""
        node_ids = [row["id"] for row in self.db.get_nodes_by_npc(npc_id)]
        if not node_ids:
            return [], None
        nodes = self._get_node_data(npc_id, node_ids)
        starts: list[str] = []
        target_start = None
        self_node = next((node for node in nodes if node.get("type") == "self" and node.get("value") == "我"), None)
        if self_node and self_node.get("node_id"):
            starts.append(str(self_node["node_id"]))
        aliases = set(get_player_name_candidates()) if target_id == "player" else {target_id, _target_name(target_id)}
        target_node = next((node for node in nodes if node.get("type") == "person" and node.get("value") in aliases), None)
        if target_node and target_node.get("node_id") and target_node["node_id"] not in starts:
            starts.append(str(target_node["node_id"]))
            target_start = str(target_node["node_id"])
        return (starts or [node_ids[0]]), target_start

    def _vector_search_once(self, npc_id: str, query: str, policy: RetrievalModePolicy) -> tuple[list[VectorSearchHit], str]:
        """本轮最多执行一次 embedding / ANN，并返回同一批锚点和兜底候选。"""
        if not self.lancedb or not hasattr(self.lancedb, "search"):
            return [], query
        from .embedding import encode_batch
        vectors = encode_batch([query])
        if vectors is None:
            return [], query
        rows = self.lancedb.search(npc_id, vectors[0].tolist(), top_k=policy.context.vector_search_top_k) or []
        hits = []
        for rank, row in enumerate(rows, start=1):
            if not row.get("node_id") or row.get("archived") or row.get("allowed", True) is False:
                continue
            similarity = row.get("similarity")
            if similarity is None:
                from ..database.lancedb_client import LanceDBClient
                similarity = LanceDBClient.normalized_similarity(row.get("_distance"))
            hits.append(VectorSearchHit(str(row["node_id"]), rank, max(0.0, min(1.0, float(similarity)))))
        return hits, query

    def _build_vector_query(self, target_id: str, location: str, context: dict[str, Any]) -> str:
        """按当前发言、近期对白、地点和短期记忆构建向量 query。"""
        turns = " ".join(_turn_text(turn) for turn in context.get("recent_turns", [])[-8:])
        parts = [context.get("query_text", ""), context.get("conversation_summary", ""), turns, location, " ".join(context.get("recent_memories", [])[:4])]
        if not context.get("query_text") and target_id == "player":
            parts.extend(PLAYER_RETRIEVAL_BASE_HINTS)
        return " ".join(str(part) for part in parts if part).strip()

    def _get_node_data(self, npc_id: str, node_ids: list[str]) -> list[dict[str, Any]]:
        """批量取节点内容。"""
        if self.lancedb and hasattr(self.lancedb, "get_batch"):
            return list(self.lancedb.get_batch(npc_id, node_ids) or [])
        return [{"node_id": node_id, "type": "event", "value": "(记忆不可用)", "importance": 0.5} for node_id in node_ids]

    def _rerank_node_data(self, nodes: list[dict[str, Any]], target_id: str, location: str, graph_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """只在已命中节点内做稳定最终重排。"""
        graph = {item.get("node_id"): item for item in graph_candidates}
        target_name = _target_name(target_id)
        zone = location.split(".", 1)[0] if location else ""
        def score(node: dict[str, Any]) -> float:
            value = render_player_tokens(str(node.get("value", "")))
            item = graph.get(node.get("node_id"), {})
            result = float(node.get("importance", 0.5)) * 0.6 + float(item.get("local_score", 0.0))
            result += {"event": 1.0, "reflection": 0.8, "emotion": 0.45}.get(node.get("type"), -0.2)
            result += 0.5 if target_name and target_name in value else 0.0
            result += min(sum(0.22 for hint in _player_retrieval_hints() if hint and hint in value), 0.88) if target_id == "player" else 0.0
            result += 0.2 if zone and zone in value else 0.0
            return result
        return sorted(nodes, key=lambda node: (-score(node), str(node.get("node_id", ""))))

    def _recover_selected_edges(self, selected_edges: list[dict[str, Any]]) -> None:
        """只恢复实际采用路径上的边清晰度。"""
        if self._clarity_recover is None:
            return
        for edge in {str(item.get("edge_id")): item for item in selected_edges if item.get("edge_id")}.values():
            try:
                self._clarity_recover(edge["edge_id"], edge.get("direction", "ab"), float(edge.get("target_importance", 0.5)))
            except Exception as error:
                logger.debug("清晰度恢复失败(%s): %s", edge.get("edge_id"), error)

    def _rebuild(self, nodes: list[dict[str, Any]], npc_id: str) -> str:
        """将最终节点重建为对白 Prompt 使用的自然语言。"""
        lines = []
        for node in nodes:
            node_type, value, importance = node.get("type", "event"), render_player_tokens(str(node.get("value", ""))), float(node.get("importance", 0.5))
            prefix = self._format_node_time(node)
            if node_type == "event":
                verb = "听说" if self._node_created_day(node) <= 0 else "记得"
                if importance < 0.7:
                    verb = "好像听说" if self._node_created_day(node) <= 0 else "好像"
                lines.append(f"- {prefix}{verb}: {value}")
            elif node_type == "reflection":
                lines.append(f"- {prefix}{value}")
            elif node_type == "emotion":
                lines.append(f"  {prefix}(当时感到{value})")
        return "\n".join(lines)

    @staticmethod
    def _format_node_time(node: dict[str, Any]) -> str:
        """格式化节点创建日，保留 Day 0。"""
        day = RetrievalEngine._node_created_day(node)
        return "[Day 0] " if day <= 0 else f"[第{day}天] "

    @staticmethod
    def _node_created_day(node: dict[str, Any]) -> int:
        """读取创建日；显式区分缺失和合法 0。"""
        try:
            raw = node.get("created_day")
            return 1 if raw is None else int(raw)
        except (TypeError, ValueError):
            return 1

    def _get_impression_context(self, npc_id: str, target_id: str) -> str:
        """读取给方向和 route Prompt 使用的短印象。"""
        row = self.db.fetchone("SELECT baseline_impression, delta_note FROM npc_impressions WHERE owner_id = ? AND target_id = ?", (npc_id, target_id)) or {}
        baseline, delta = row.get("baseline_impression", ""), row.get("delta_note", "")
        return f"{baseline} 今天刚发生：{delta[:40]}" if delta else baseline or "暂无特别判断"

    def _write_retrieval_log(self, npc_id: str, target_id: str, mode: str, game_time: str, location: str, graph_node_count: int, vector_fallback_count: int, final_nodes: list[dict[str, Any]], selected_edges: list[dict[str, Any]], diagnostics: dict[str, Any], elapsed_sec: float) -> None:
        """写入旧表兼容日志；完整结构化 trace 存于 trace provider。"""
        try:
            self.db.insert_retrieval_log({"id": f"ret_{uuid.uuid4().hex[:10]}", "npc_id": npc_id, "target_id": target_id, "mode": mode, "game_time": game_time, "location": location, "graph_nodes": graph_node_count, "vector_fallback": vector_fallback_count, "final_nodes": len(final_nodes), "selected_edges": len(selected_edges), "llm_route_calls": int(diagnostics.get("llm_route_calls", 0)), "local_route_skips": int(diagnostics.get("local_route_skips", 0)), "hit_merged_count": sum(1 for node in final_nodes if "_merged_" in str(node.get("node_id", ""))), "elapsed_sec": round(elapsed_sec, 4)})
        except Exception as error:
            logger.debug("检索旧日志写入失败: %s", error)

    def _build_trace(self, trace_id, request, mode, policy, resolution, starts, vector_hits, edges, assembly, query_plan, vector_query, layer_stats, counters, candidates, stop_reason, failure_reason, degraded, elapsed, fallback_ids, context_budget):
        """将内部 outcome 映射为不含隐私长文本的 trace。"""
        direction = {
            "entity_mentions": resolution.direction.entity_mentions,
            "location_mentions": resolution.direction.location_mentions,
            "themes": resolution.direction.themes,
            "relation_facets": resolution.direction.relation_facets,
            "time_scope": resolution.direction.time_scope,
            "recall_intent": resolution.direction.recall_intent,
            "negative_directions": resolution.direction.negative_directions,
            "retrieval_query": resolution.direction.retrieval_query[:240],
            "query_constraints": resolution.direction.query_constraints,
        } if resolution else {}
        return RetrievalTrace(
            retrieval_trace_id=trace_id, npc_id=request.npc_id,
            target_id=request.conversation_participant_ids[0] if request.conversation_participant_ids else "player",
            mode=mode, strategy=policy.strategy.value, config_version=policy.version,
            policy_summary={
                "strategy": policy.strategy.value,
                "final_memory_limit": policy.context.final_memory_limit,
                "final_context_max_chars": policy.context.final_context_max_chars,
                "max_direction_context_chars": policy.context.max_direction_context_chars,
                "max_depth": policy.local_search.budget.max_depth,
                "beam_width": policy.local_search.budget.beam_width,
                "max_neighbors_per_node": policy.local_search.budget.max_neighbors_per_node,
                "max_expanded_edges": policy.local_search.budget.max_expanded_edges,
                "context_budget": context_budget,
            },
            direction_source=resolution.source if resolution else "not_applicable", direction=direction,
            mentions=[{"text": item.text, "entity_id": item.entity_id, "entity_type": item.entity_type, "source": item.source, "confidence": item.confidence} for item in resolution.mentions] if resolution else [],
            start_node_ids=starts,
            target_anchors=[{"node_id": hit.node_id, "usage": "anchor_discovery"} for hit in vector_hits],
            layer_stats=layer_stats,
            path_evidence=[{"node_id": item.get("node_id"), "edge_id": item.get("edge_id"), "score": item.get("local_score", 0.0), "score_components": item.get("score_components", {})} for item in edges],
            selected_edge_ids=[str(item.get("edge_id")) for item in edges if item.get("edge_id")],
            retrieved_node_ids=[entry.node_id for entry in assembly.entries], vector_query_preview=vector_query[:512],
            vector_hit_usage=[{"node_id": hit.node_id, "rank": hit.rank, "similarity": hit.similarity, "usage": "anchor_discovery"} for hit in vector_hits] + [{"node_id": node_id, "usage": "content_fallback"} for node_id in fallback_ids],
            diagnostics={"candidate_count": len(candidates), "expanded_edges": counters.get("expanded_edges", counters.get("candidate_edges", 0)), "original_query_preview": query_plan.original_query[:240], "original_query_chars": len(query_plan.original_query), "retrieval_query_preview": query_plan.retrieval_query[:240], "retrieval_query_chars": len(query_plan.retrieval_query), "retrieval_query_source": query_plan.retrieval_query_source, "query_constraints": query_plan.query_constraints, "selected_recent_turn_preview": query_plan.selected_recent_turn[:240], "selected_recent_turn_chars": len(query_plan.selected_recent_turn), "selection_reason": query_plan.selection_reason, "embedding_query_preview": query_plan.embedding_query[:512], "embedding_query_chars": len(query_plan.embedding_query), "direction_validation_errors": resolution.validation_errors if resolution else [], "direction_calibrations": resolution.calibrations if resolution else [], "query_fallback_reason": query_plan.fallback_reason, "graph_candidate_ids": [str(item.get("node_id")) for item in candidates], "final_entries": [{"node_id": entry.node_id, "type": entry.node_type, "score": entry.score, "score_components": [{"name": name, "value": value} for name, value in entry.score_components.items()], "rendered_chars": len(entry.rendered_text)} for entry in assembly.entries], "evicted_entries": assembly.evicted_entries, "final_entry_count": len(assembly.entries), "final_context_chars": len(assembly.context_text)},
            stop_reason=stop_reason, failure_reason=failure_reason, degraded_to_local=degraded, elapsed_sec=round(elapsed, 6),
        )

    def force_recall(self, npc_id: str, query: str) -> list[dict[str, Any]]:
        """保留旧的显式 BGE 全量回忆入口。"""
        if not self.lancedb or not hasattr(self.lancedb, "search"):
            return []
        from .embedding import encode_batch
        vectors = encode_batch([query])
        return [] if vectors is None else self.lancedb.search(npc_id, vectors[0].tolist(), top_k=10, include_archived=True)

    # 以下三个入口只服务旧测试 / 调试脚本，业务路径不再在 facade 内实现图算法。
    def _collect_candidate_edges(self, npc_id, target_id, frontier, target_start_id, route_context, visited_nodes, visited_edges, max_edges_per_hop):
        """兼容旧测试的候选收集委托。"""
        from .retrieval_contracts import DeepSearchRequest
        compatibility_request = route_context.get("_request") or RetrievalRequest(
            npc_id=npc_id,
            conversation_participant_ids=[target_id],
            query_text=str(route_context.get("query_text", "")),
            conversation_summary=str(route_context.get("conversation_summary", "")),
            recent_turns=list(route_context.get("recent_turns", [])),
        )
        direction = route_context.get("_direction") or LocalDirectionProvider().provide(compatibility_request, route_context).direction
        policy = self._effective_policy(route_context.get("mode", "player_dialogue")).local_search
        policy = replace(policy, budget=replace(policy.budget, max_neighbors_per_node=max_edges_per_hop))
        return self.deep_retriever._collect_candidates(DeepSearchRequest(npc_id, target_id, list(frontier), target_start_id, direction, policy), list(frontier), set(visited_nodes), set(visited_edges), route_context.setdefault("_counters", {"expanded_edges": 0, "filtered_archived": 0, "filtered_forbidden": 0, "filtered_loop": 0, "filtered_low_score": 0}))

    @staticmethod
    def _can_use_local_route(route_context: dict[str, Any], candidate_edges: list[dict[str, Any]], max_select: int) -> bool:
        """兼容旧断言；正式 llm_full_route 不调用此跳过逻辑。"""
        if len(candidate_edges) <= max_select:
            return True
        return float(candidate_edges[max_select - 1].get("local_score", 0.0)) >= float(route_context.get("local_route_min_score", 0.0))


retrieval_engine: RetrievalEngine | None = None


def init_retrieval(db: SQLiteClient, lancedb=None, clarity_recover=None) -> RetrievalEngine:
    """初始化全局检索 facade。"""
    global retrieval_engine
    retrieval_engine = RetrievalEngine(db, lancedb, clarity_recover=clarity_recover)
    return retrieval_engine
