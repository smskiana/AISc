"""记忆检索 YAML 配置的读取、严格校验和 typed policy 注册表。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .retrieval_contracts import (
    LocalSearchPolicy,
    LlmRoutePolicy,
    RetrievalExecutionOptions,
    RetrievalModePolicy,
    RetrievalStrategy,
    SearchBudget,
)


DEFAULT_SCORING = {
    "direction_relevance": 0.24,
    "entity_alignment": 0.18,
    "relation_facet_alignment": 0.12,
    "edge_clarity": 0.10,
    "time_alignment": 0.08,
    "source_reliability": 0.08,
    "target_context": 0.06,
    "node_importance": 0.06,
    "novel_evidence": 0.08,
    "depth_penalty_per_extra_hop": 0.06,
    "repeated_topic_penalty": 0.12,
    "uncertainty_penalty": 0.10,
}

MODE_NAMES = {"player_dialogue", "npc_dialogue", "nightly_impression"}
STRATEGY_NAMES = {item.value for item in RetrievalStrategy}
CONTEXT_KEYS = {
    "recent_turn_limit", "recent_memory_limit", "memory_summary_chars",
    "conversation_summary_chars", "max_direction_context_chars",
}
LOCAL_KEYS = {
    "max_depth", "beam_width", "max_neighbors_per_node", "max_expanded_edges",
    "max_anchor_count", "max_answer_candidates", "min_path_score", "early_stop_margin",
}
LLM_KEYS = {
    "max_hops", "max_frontier_nodes", "max_neighbors_per_node", "max_candidate_edges",
    "selected_edges_per_hop", "max_llm_route_calls", "candidate_summary_chars",
    "max_route_prompt_chars",
}
RESULT_KEYS = {"vector_search_top_k", "vector_fallback_limit", "final_memory_limit"}
QUERY_KEYS = {"retrieval_query_chars", "selected_recent_turn_limit", "selected_recent_turn_chars", "embedding_query_chars", "final_context_max_chars"}
FINAL_SCORING = {
    "query_semantic_similarity": 0.42,
    "graph_path_relevance": 0.25,
    "explicit_entity_alignment": 0.12,
    "recency": 0.08,
    "importance": 0.08,
    "node_type_prior": 0.05,
}
MAX_SAFE = {
    "recent_turn_limit": 32, "recent_memory_limit": 32, "memory_summary_chars": 512,
    "conversation_summary_chars": 12000, "max_direction_context_chars": 16000,
    "max_depth": 16, "beam_width": 64, "max_neighbors_per_node": 64,
    "max_expanded_edges": 1024, "max_anchor_count": 32, "max_answer_candidates": 128,
    "max_hops": 16, "max_frontier_nodes": 64, "max_candidate_edges": 64,
    "selected_edges_per_hop": 32, "max_llm_route_calls": 16,
    "candidate_summary_chars": 512, "max_route_prompt_chars": 16000,
    "vector_search_top_k": 64, "vector_fallback_limit": 32, "final_memory_limit": 32,
    "retrieval_query_chars": 1024, "selected_recent_turn_limit": 1,
    "selected_recent_turn_chars": 1024, "embedding_query_chars": 2048,
    "final_context_max_chars": 12000,
}


class RetrievalPolicyRegistry:
    """启动时读取一次检索配置，并只暴露已校验的 mode policy。"""

    def __init__(self, config_path: str | Path | None = None, payload: dict[str, Any] | None = None):
        """从 YAML 路径或测试注入的内存 payload 构建注册表。"""
        self.config_path = Path(config_path) if config_path else Path(__file__).resolve().parents[2] / "config" / "memory_retrieval.yaml"
        raw = payload if payload is not None else self._load()
        self.version = self._validate_root(raw)
        self._policies = {mode: self._build_policy(mode, data) for mode, data in raw["modes"].items()}

    def _load(self) -> dict[str, Any]:
        """读取严格要求存在的 YAML 配置。"""
        try:
            with self.config_path.open("r", encoding="utf-8") as stream:
                data = yaml.safe_load(stream) or {}
        except (OSError, yaml.YAMLError) as error:
            raise ValueError(f"memory_retrieval_config_error:{error}") from error
        return data

    @staticmethod
    def _validate_root(raw: dict[str, Any]) -> int:
        """校验根级字段、版本和业务模式集合。"""
        if not isinstance(raw, dict) or set(raw) != {"version", "modes"}:
            raise ValueError("memory_retrieval_config_unknown_root_field")
        if raw.get("version") != 1:
            raise ValueError("memory_retrieval_config_invalid_version")
        if not isinstance(raw.get("modes"), dict) or set(raw["modes"]) != MODE_NAMES:
            raise ValueError("memory_retrieval_config_modes_must_match_supported_modes")
        return 1

    def _build_policy(self, mode: str, raw: dict[str, Any]) -> RetrievalModePolicy:
        """将一个业务模式的嵌套字典转换为不可变 DTO。"""
        if not isinstance(raw, dict) or set(raw) - {"strategy", "context", "local_search", "llm_route", "result", "query", "scoring", "final_scoring"}:
            raise ValueError(f"{mode}:unknown_policy_field")
        strategy = raw.get("strategy")
        if strategy not in STRATEGY_NAMES:
            raise ValueError(f"{mode}:unknown_strategy:{strategy}")
        context = self._section(mode, raw, "context", CONTEXT_KEYS)
        local = self._section(mode, raw, "local_search", LOCAL_KEYS)
        llm_route = self._section(mode, raw, "llm_route", LLM_KEYS)
        result = self._section(mode, raw, "result", RESULT_KEYS)
        query = self._section(mode, raw, "query", QUERY_KEYS)
        scoring = dict(DEFAULT_SCORING)
        if "scoring" in raw:
            if not isinstance(raw["scoring"], dict) or set(raw["scoring"]) != set(DEFAULT_SCORING):
                raise ValueError(f"{mode}:scoring_must_have_complete_fields")
            scoring = {key: self._number(mode, f"scoring.{key}", value, 0.0, 1.0) for key, value in raw["scoring"].items()}
        final_scoring = dict(FINAL_SCORING)
        if "final_scoring" in raw:
            if not isinstance(raw["final_scoring"], dict) or set(raw["final_scoring"]) != set(FINAL_SCORING):
                raise ValueError(f"{mode}:final_scoring_must_have_complete_fields")
            final_scoring = {key: self._number(mode, f"final_scoring.{key}", value, 0.0, 1.0) for key, value in raw["final_scoring"].items()}
        if abs(sum(final_scoring.values()) - 1.0) > 0.000001:
            raise ValueError(f"{mode}:final_scoring_must_sum_to_one")
        if final_scoring["node_type_prior"] > 0.05:
            raise ValueError(f"{mode}:node_type_prior_must_not_exceed_0_05")
        local_budget = SearchBudget(
            max_depth=self._integer(mode, "local_search.max_depth", local["max_depth"]),
            beam_width=self._integer(mode, "local_search.beam_width", local["beam_width"]),
            max_neighbors_per_node=self._integer(mode, "local_search.max_neighbors_per_node", local["max_neighbors_per_node"]),
            max_expanded_edges=self._integer(mode, "local_search.max_expanded_edges", local["max_expanded_edges"]),
            max_anchor_count=self._integer(mode, "local_search.max_anchor_count", local["max_anchor_count"]),
            max_answer_candidates=self._integer(mode, "local_search.max_answer_candidates", local["max_answer_candidates"]),
            min_path_score=self._number(mode, "local_search.min_path_score", local["min_path_score"], 0.0, 1.0),
            early_stop_margin=self._number(mode, "local_search.early_stop_margin", local["early_stop_margin"], 0.0, 1.0),
        )
        route_policy = LlmRoutePolicy(
            max_hops=self._integer(mode, "llm_route.max_hops", llm_route["max_hops"]),
            max_frontier_nodes=self._integer(mode, "llm_route.max_frontier_nodes", llm_route["max_frontier_nodes"]),
            max_neighbors_per_node=self._integer(mode, "llm_route.max_neighbors_per_node", llm_route["max_neighbors_per_node"]),
            max_candidate_edges=self._integer(mode, "llm_route.max_candidate_edges", llm_route["max_candidate_edges"]),
            selected_edges_per_hop=self._integer(mode, "llm_route.selected_edges_per_hop", llm_route["selected_edges_per_hop"]),
            max_llm_route_calls=self._integer(mode, "llm_route.max_llm_route_calls", llm_route["max_llm_route_calls"]),
            candidate_summary_chars=self._integer(mode, "llm_route.candidate_summary_chars", llm_route["candidate_summary_chars"]),
            max_route_prompt_chars=self._integer(mode, "llm_route.max_route_prompt_chars", llm_route["max_route_prompt_chars"]),
        )
        if route_policy.selected_edges_per_hop > route_policy.max_candidate_edges:
            raise ValueError(f"{mode}:selected_edges_must_not_exceed_candidates")
        if route_policy.max_llm_route_calls > route_policy.max_hops:
            raise ValueError(f"{mode}:llm_calls_must_not_exceed_hops")
        if query["selected_recent_turn_limit"] > 1:
            raise ValueError(f"{mode}:selected_recent_turn_limit_must_not_exceed_one")
        if query["retrieval_query_chars"] > query["embedding_query_chars"] or query["selected_recent_turn_chars"] > query["embedding_query_chars"]:
            raise ValueError(f"{mode}:query_segment_must_not_exceed_embedding_budget")
        if query["final_context_max_chars"] < 64:
            raise ValueError(f"{mode}:final_context_max_chars_too_small")
        return RetrievalModePolicy(
            mode=mode,
            strategy=RetrievalStrategy(strategy),
            context=RetrievalExecutionOptions(
                recent_turn_limit=self._integer(mode, "context.recent_turn_limit", context["recent_turn_limit"]),
                recent_memory_limit=self._integer(mode, "context.recent_memory_limit", context["recent_memory_limit"]),
                memory_summary_chars=self._integer(mode, "context.memory_summary_chars", context["memory_summary_chars"]),
                conversation_summary_chars=self._integer(mode, "context.conversation_summary_chars", context["conversation_summary_chars"]),
                max_direction_context_chars=self._integer(mode, "context.max_direction_context_chars", context["max_direction_context_chars"]),
                vector_search_top_k=self._integer(mode, "result.vector_search_top_k", result["vector_search_top_k"]),
                vector_fallback_limit=self._integer(mode, "result.vector_fallback_limit", result["vector_fallback_limit"]),
                final_memory_limit=self._integer(mode, "result.final_memory_limit", result["final_memory_limit"]),
                retrieval_query_chars=self._integer(mode, "query.retrieval_query_chars", query["retrieval_query_chars"]),
                selected_recent_turn_limit=self._integer(mode, "query.selected_recent_turn_limit", query["selected_recent_turn_limit"]),
                selected_recent_turn_chars=self._integer(mode, "query.selected_recent_turn_chars", query["selected_recent_turn_chars"]),
                embedding_query_chars=self._integer(mode, "query.embedding_query_chars", query["embedding_query_chars"]),
                final_context_max_chars=self._integer(mode, "query.final_context_max_chars", query["final_context_max_chars"]),
            ),
            local_search=LocalSearchPolicy(local_budget),
            llm_route=route_policy,
            scoring=scoring,
            final_scoring=final_scoring,
            version=self.version,
        )

    def _section(self, mode: str, raw: dict[str, Any], name: str, allowed: set[str]) -> dict[str, Any]:
        """校验一个参数块必须完整且不含未知字段。"""
        value = raw.get(name)
        if not isinstance(value, dict) or set(value) != allowed:
            raise ValueError(f"{mode}:{name}_fields_must_be_complete_and_known")
        return value

    @staticmethod
    def _number(mode: str, name: str, value: Any, minimum: float, maximum: float) -> float:
        """校验有限范围内的数值，拒绝布尔值和隐式类型转换。"""
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= float(value) <= maximum:
            raise ValueError(f"{mode}:{name}_out_of_range")
        return float(value)

    @staticmethod
    def _integer(mode: str, name: str, value: Any) -> int:
        """校验非负整数和项目安全上限。"""
        key = name.rsplit(".", 1)[-1]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > MAX_SAFE[key]:
            raise ValueError(f"{mode}:{name}_invalid")
        return value

    def get(self, mode: str) -> RetrievalModePolicy:
        """返回指定业务模式的已校验 policy。"""
        try:
            return self._policies[mode]
        except KeyError as error:
            raise KeyError(f"unknown_retrieval_mode:{mode}") from error

    def all(self) -> dict[str, RetrievalModePolicy]:
        """返回只读意义上的 policy 映射副本，供评估和诊断使用。"""
        return dict(self._policies)
