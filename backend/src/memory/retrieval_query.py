"""单次向量检索 query 的纯函数规划模块。"""
from __future__ import annotations

import re
from typing import Any

from .retrieval_contracts import DirectionResolution, RetrievalModePolicy, RetrievalQueryPlan, RetrievalRequest
from .retrieval_direction import LOCATION_ALIASES, NPC_NAMES


_TIME_PATTERN = re.compile(r"(?:第\s*\d+\s*天|day\s*\d+|\d{1,2}\s*[:：]\s*\d{2})", re.IGNORECASE)
_PRONOUNS = ("她", "他", "那里", "那个人", "上次你说")


def _turn_text(turn: Any) -> str:
    """提取近期对白的正文。"""
    return str(turn.get("text", "")) if isinstance(turn, dict) else str(getattr(turn, "text", turn))


class RetrievalQueryPlanner:
    """收口检索想法校验、近期对白选择和固定标签 query 组装。"""

    def plan(self, request: RetrievalRequest, resolution: DirectionResolution, policy: RetrievalModePolicy) -> RetrievalQueryPlan:
        """依据校准方向生成唯一 embedding query，绝不混入场景或摘要。"""
        original = str(request.query_text or "").strip()
        explicit = self._explicit_entities(original)
        retrieval_query, source, fallback = self._validated_retrieval_query(original, resolution, policy, explicit)
        selected_turn, selection_reason = self._select_recent_turn(original, request.recent_turns, explicit, policy)
        query, exceeded = self._assemble(original, retrieval_query, selected_turn, policy)
        return RetrievalQueryPlan(
            original_query=original,
            retrieval_query=retrieval_query,
            retrieval_query_source=source,
            query_constraints=list(resolution.direction.query_constraints),
            explicit_entities=explicit,
            selected_recent_turn=selected_turn,
            selection_reason=selection_reason,
            embedding_query=query,
            fallback_reason=fallback,
            original_query_exceeds_budget=exceeded,
        )

    @staticmethod
    def _explicit_entities(text: str) -> list[str]:
        """从当前问题提取权威稳定人物和地点 mention。"""
        found: list[str] = []
        for name in NPC_NAMES.values():
            if name in text and name not in found:
                found.append(name)
        for aliases in LOCATION_ALIASES.values():
            for alias in aliases:
                if alias in text and alias not in found:
                    found.append(alias)
        return found

    def _validated_retrieval_query(self, original: str, resolution: DirectionResolution, policy: RetrievalModePolicy, explicit: list[str]) -> tuple[str, str, str]:
        """拒绝空、超长、越权稳定实体或新增精确时间的 LLM 想法。"""
        candidate = str(resolution.direction.retrieval_query or "").strip()
        if not candidate:
            return original, "original_query", "retrieval_query_empty"
        if len(candidate) > policy.context.retrieval_query_chars:
            return original, "original_query", "retrieval_query_too_long"
        candidate_entities = self._explicit_entities(candidate)
        if any(item not in explicit for item in candidate_entities):
            return original, "original_query", "retrieval_query_entity_mismatch"
        original_times = set(match.group(0).lower().replace(" ", "") for match in _TIME_PATTERN.finditer(original))
        candidate_times = set(match.group(0).lower().replace(" ", "") for match in _TIME_PATTERN.finditer(candidate))
        if candidate_times - original_times:
            return original, "original_query", "retrieval_query_fact_risk"
        return candidate, "llm_guided" if resolution.source == "llm" else "local", ""

    def _select_recent_turn(self, query: str, turns: list[Any], explicit: list[str], policy: RetrievalModePolicy) -> tuple[str, str]:
        """最多选择一条相关对白，普通明确问题不会被无关上下文污染。"""
        if policy.context.selected_recent_turn_limit == 0:
            return "", "policy_disabled"
        for turn in reversed(turns):
            text = _turn_text(turn).strip()
            if text and any(entity in text for entity in explicit):
                return text[: policy.context.selected_recent_turn_chars], "explicit_entity_overlap"
        if any(token in query for token in _PRONOUNS):
            for turn in reversed(turns):
                text = _turn_text(turn).strip()
                if text and self._explicit_entities(text):
                    return text[: policy.context.selected_recent_turn_chars], "pronoun_resolved_entity"
        return "", "no_relevant_turn"

    @staticmethod
    def _sentence_prefix(text: str, limit: int) -> str:
        """在完整句边界压缩检索想法，不产生半句话。"""
        if len(text) <= limit:
            return text
        prefix = text[:limit]
        boundary = max(prefix.rfind(token) for token in ("。", "！", "？", "!", "?"))
        return prefix[: boundary + 1].strip() if boundary >= 0 else ""

    def _assemble(self, original: str, retrieval_query: str, selected_turn: str, policy: RetrievalModePolicy) -> tuple[str, bool]:
        """按既定淘汰顺序组装标签 query，并保持当前问题完整。"""
        limit = policy.context.embedding_query_chars
        if len(original) > limit:
            return original, True
        parts = [f"当前问题：{original}", f"检索想法：{retrieval_query}"]
        if selected_turn:
            parts.append(f"相关近期对白：{selected_turn}")
        query = "\n".join(parts)
        if len(query) <= limit:
            return query, False
        parts = parts[:2]
        query = "\n".join(parts)
        if len(query) <= limit:
            return query, False
        remaining = max(0, limit - len(parts[0]) - len("检索想法：") - 1)
        compact = self._sentence_prefix(retrieval_query, remaining)
        return "\n".join((parts[0], f"检索想法：{compact}" if compact else "检索想法：")), False
