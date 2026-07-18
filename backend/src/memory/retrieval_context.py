"""最终原子记忆条目的去重、评分、渲染和预算组装模块。"""
from __future__ import annotations

import re
from typing import Any

from ..dialogue.player_name import render_player_tokens
from .retrieval_contracts import FailureReason, RetrievalContextAssembly, RetrievedMemoryEntry, RetrievalModePolicy, RetrievalQueryPlan, VectorSearchHit


class RetrievalContextAssembler:
    """以统一六分量 profile 选择完整记忆条目，避免类型先验压过相关性。"""

    def assemble(self, candidates: list[dict[str, Any]], query_plan: RetrievalQueryPlan, vector_hits: list[VectorSearchHit], request_time: str, policy: RetrievalModePolicy) -> RetrievalContextAssembly:
        """合并候选、按稳定 tie-break 排序并贪心装入完整条目。"""
        hit_map = {hit.node_id: hit for hit in vector_hits}
        merged: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            node_id = str(candidate.get("node_id", ""))
            if node_id and node_id not in merged:
                merged[node_id] = candidate
        entries = [self._entry(node, query_plan, hit_map.get(node_id), request_time, policy) for node_id, node in merged.items()]
        entries.sort(key=lambda entry: (-entry.score, -entry.score_components["graph_path_relevance"], hit_map.get(entry.node_id, VectorSearchHit(entry.node_id, 999999, 0.0)).rank, entry.node_id))
        kept: list[RetrievedMemoryEntry] = []
        evicted: list[dict[str, str]] = []
        chars = 0
        for entry in entries:
            if len(kept) >= policy.context.final_memory_limit:
                evicted.append({"node_id": entry.node_id, "reason": "final_memory_limit"})
            elif chars + len(entry.rendered_text) + (1 if kept else 0) > policy.context.final_context_max_chars:
                evicted.append({"node_id": entry.node_id, "reason": "entry_exceeds_context_budget"})
            else:
                kept.append(entry)
                chars += len(entry.rendered_text) + (1 if len(kept) > 1 else 0)
        failure = FailureReason.BUDGET_EXHAUSTED.value if entries and not kept else FailureReason.NONE.value
        return RetrievalContextAssembly(kept, evicted, "\n".join(entry.rendered_text for entry in kept), failure)

    def _entry(self, node: dict[str, Any], plan: RetrievalQueryPlan, hit: VectorSearchHit | None, request_time: str, policy: RetrievalModePolicy) -> RetrievedMemoryEntry:
        """计算单节点六分量分数并按节点类型安全渲染。"""
        value = render_player_tokens(str(node.get("value", "")))
        graph_score = self._clamp(float(node.get("local_score", 0.0) or 0.0))
        semantic = hit.similarity if hit else 0.0
        entity = 1.0 if any(item and item in value for item in plan.explicit_entities) else 0.0
        recency = self._recency(node.get("created_day"), request_time)
        importance = self._clamp(float(node.get("importance", 0.5) or 0.5))
        type_prior = {"event": 1.0, "reflection": 0.8, "emotion": 0.6}.get(str(node.get("type", "")), 0.5)
        raw = {
            "query_semantic_similarity": semantic,
            "graph_path_relevance": graph_score,
            "explicit_entity_alignment": entity,
            "recency": recency,
            "importance": importance,
            "node_type_prior": type_prior,
        }
        components = {key: round(raw[key], 6) for key in raw}
        score = sum(policy.final_scoring[key] * raw[key] for key in raw)
        return RetrievedMemoryEntry(str(node["node_id"]), str(node.get("type", "event")), self._render(node), round(score, 6), components)

    @staticmethod
    def _render(node: dict[str, Any]) -> str:
        """只渲染节点正文与已有时间，不从人物或地点名称推断事实。"""
        value = render_player_tokens(str(node.get("value", "")))
        try:
            day = int(node.get("created_day", 1))
        except (TypeError, ValueError):
            day = 1
        prefix = "[Day 0] " if day <= 0 else f"[第{day}天] "
        node_type = str(node.get("type", "event"))
        if node_type == "event":
            return f"- {prefix}记得：{value}"
        if node_type == "reflection":
            return f"- {prefix}{value}"
        if node_type == "emotion":
            return f"- {prefix}(当时感到{value})"
        return f"- {prefix}{value}"

    @staticmethod
    def _recency(created_day: Any, request_time: str) -> float:
        """根据请求日归一化节点时效，缺失值保持中性。"""
        try:
            day = int(created_day)
            match = re.search(r"\d+", str(request_time))
            request_day = int(match.group(0)) if match else day
            return 1.0 / (1.0 + max(0, request_day - day) / 30.0)
        except (TypeError, ValueError):
            return 0.5

    @staticmethod
    def _clamp(value: float) -> float:
        """限制外部存储或图层分数到标准范围。"""
        return max(0.0, min(1.0, value))
