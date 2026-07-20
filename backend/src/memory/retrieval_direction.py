"""记忆检索方向解析：本地确定性 provider、一次方向 LLM 和统一校验。"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..dialogue.player_name import get_player_name_candidates
from ..prompting import PromptAssembler
from .retrieval_contracts import (
    DirectionProvider,
    DirectionResolution,
    QueryConstraint,
    RecallIntent,
    RelationFacet,
    ResolvedMention,
    RetrievalDirection,
    RetrievalRequest,
    SourcePreference,
    Theme,
    TimeScope,
)

logger = logging.getLogger("sakurabashi.retrieval.direction")

NPC_NAMES = {
    "sakura": "鹿岛樱", "chihaya": "千早", "kazuha": "和叶",
    "tatsunosuke": "龙之介", "kujo": "九条莲",
}
LOCATION_ALIASES = {
    "player_cafe": ("喫茶店", "咖啡店"), "flower_shop": ("花店",),
    "bakery": ("面包店", "烘焙店"), "bookstore": ("旧书店", "书店"),
    "wagashi": ("和果子店",), "police_box": ("派出所",),
    "street": ("商店街", "樱桥通"), "park": ("小公园",),
    "riverside": ("河边", "樱花道"),
}
THEME_VALUES = {item.value for item in Theme}
RELATION_VALUES = {item.value for item in RelationFacet}
TIME_VALUES = {item.value for item in TimeScope}
SOURCE_VALUES = {item.value for item in SourcePreference}
INTENT_VALUES = {item.value for item in RecallIntent}
QUERY_CONSTRAINT_VALUES = {item.value for item in QueryConstraint}
NEGATIVE_VALUES = {
    "unrelated_player_background", "unrelated_private_memory", "stale_location", "unrelated_person",
}


def _strip_json_fence(raw: str) -> str:
    """去掉方向 LLM 可能返回的 markdown JSON 包装。"""
    text = str(raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        return "\n".join(lines[1:-1]).strip() if len(lines) >= 2 else ""
    return text


def _turn_text(turn: Any) -> str:
    """提取近期对白文本而不依赖对话层实体状态。"""
    if isinstance(turn, dict):
        return str(turn.get("text", ""))
    return str(getattr(turn, "text", turn))


class DirectionResolver:
    """封装方向 provider 调用、JSON 清洗和 mention 解析。"""

    def __init__(self, prompt_assembler: PromptAssembler | None = None):
        """注入统一 Prompt 组装器。"""
        self.prompt_assembler = prompt_assembler or PromptAssembler()

    def resolve(self, request: RetrievalRequest, context: dict[str, Any], provider: DirectionProvider) -> DirectionResolution:
        """通过一个 provider 生成并校验完整方向契约。"""
        result = provider.provide(request, context)
        direction, errors = self._validate_direction(result.direction)
        direction, calibrations = self._calibrate_direction(request, direction)
        mentions = self._resolve_mentions(direction, request, context)
        return DirectionResolution(
            direction=direction,
            mentions=mentions,
            source=result.source,
            failure_reason=result.failure_reason,
            validation_errors=[*result.validation_errors, *errors],
            calibrations=calibrations,
            llm_output_summary=result.llm_output_summary,
        )

    def build_context(self, request: RetrievalRequest, limits: Any, recent_memories: list[str]) -> dict[str, Any]:
        """按固定优先级裁剪方向输入，保留当前问题和明确 mention。"""
        query = str(request.query_text or "")
        turns = list(request.recent_turns or [])[: int(limits.recent_turn_limit)]
        summary = str(request.conversation_summary or "")[: int(limits.conversation_summary_chars)]
        memories = [str(item)[: int(limits.memory_summary_chars)] for item in recent_memories[: int(limits.recent_memory_limit)]]
        context = {
            "query_text": query, "conversation_summary": summary,
            "recent_turns": [{"speaker_id": getattr(turn, "speaker_id", "?"), "text": _turn_text(turn)[:160]} for turn in turns],
            "recent_memories": memories,
            "location": request.location_id or "street",
            "game_time": request.game_time or "未知",
            "participant_ids": list(request.conversation_participant_ids),
        }
        return self._trim_context(context, int(limits.max_direction_context_chars))

    @staticmethod
    def _trim_context(context: dict[str, Any], limit: int) -> dict[str, Any]:
        """稳定裁剪动态上下文，当前问题和命中 mention 的对白优先。"""
        original_turn_count = len(context.get("recent_turns", []))
        original_memory_count = len(context.get("recent_memories", []))
        original_chars = len(json.dumps(context, ensure_ascii=False))
        query = str(context.get("query_text", ""))
        turns = list(context.get("recent_turns", []))
        keep = [turn for turn in turns if any(token and token in str(turn.get("text", "")) for token in (query,))]
        for turn in reversed(turns):
            if turn not in keep:
                keep.append(turn)
        context["recent_turns"] = keep
        while len(json.dumps(context, ensure_ascii=False)) > limit and context["recent_memories"]:
            context["recent_memories"].pop()
        while len(json.dumps(context, ensure_ascii=False)) > limit and context["recent_turns"]:
            context["recent_turns"].pop()
        if len(json.dumps(context, ensure_ascii=False)) > limit:
            context["conversation_summary"] = str(context.get("conversation_summary", ""))[: max(0, limit // 5)]
        context["_context_budget"] = {
            "original_turn_count": original_turn_count,
            "provided_turn_count": len(context.get("recent_turns", [])),
            "original_memory_count": original_memory_count,
            "provided_memory_count": len(context.get("recent_memories", [])),
            "original_chars": original_chars,
            "provided_chars": len(json.dumps(context, ensure_ascii=False)),
            "limit_chars": limit,
            "eviction_reason": "current_query_and_mention_priority" if original_chars > len(json.dumps(context, ensure_ascii=False)) else "none",
        }
        return context

    def _validate_direction(self, direction: RetrievalDirection) -> tuple[RetrievalDirection, list[str]]:
        """清洗非法枚举并保留可用方向。"""
        errors: list[str] = []

        def clean_list(values: Any, allowed: set[str], name: str) -> list[str]:
            """过滤列表枚举并去重。"""
            if not isinstance(values, list):
                errors.append(f"{name}_not_array")
                return []
            result: list[str] = []
            for value in values:
                if isinstance(value, str) and value in allowed and value not in result:
                    result.append(value)
                elif not isinstance(value, str) or value not in allowed:
                    errors.append(f"invalid_{name}:{value}")
            return result

        def clean_scalar(value: Any, allowed: set[str], fallback: str, name: str) -> str:
            """把错误形状或非法值的标量枚举稳定降级。"""
            if isinstance(value, str) and value in allowed:
                return value
            errors.append(f"invalid_{name}:{value}")
            return fallback

        def clean_mentions(values: Any, name: str) -> list[str]:
            """过滤错误形状的实体或地点文本数组。"""
            if not isinstance(values, list):
                errors.append(f"{name}_not_array")
                return []
            return [item[:80] for item in values if isinstance(item, str) and item.strip()][:8]

        themes = clean_list(direction.themes, THEME_VALUES, "theme") or [Theme.GENERAL.value]
        relations = clean_list(direction.relation_facets, RELATION_VALUES, "relation_facet")
        sources = clean_list(direction.source_preferences, SOURCE_VALUES, "source_preference")
        negatives = clean_list(direction.negative_directions, NEGATIVE_VALUES, "negative_direction")
        constraints = clean_list(direction.query_constraints, QUERY_CONSTRAINT_VALUES, "query_constraint")
        time_scope = clean_scalar(direction.time_scope, TIME_VALUES, TimeScope.ANY.value, "time_scope")
        intent = clean_scalar(direction.recall_intent, INTENT_VALUES, RecallIntent.GENERAL_RECALL.value, "recall_intent")
        return RetrievalDirection(
            entity_mentions=clean_mentions(direction.entity_mentions, "entity_mentions"),
            location_mentions=clean_mentions(direction.location_mentions, "location_mentions"),
            themes=themes, relation_facets=relations, time_scope=time_scope,
            source_preferences=sources, recall_intent=intent, negative_directions=negatives,
            retrieval_query=str(direction.retrieval_query or "").strip()[:512], query_constraints=constraints,
        ), errors

    def _calibrate_direction(self, request: RetrievalRequest, direction: RetrievalDirection) -> tuple[RetrievalDirection, list[str]]:
        """以当前问题的本地明确实体和定位词收紧结构合法但语义泛化的方向。"""
        query = str(request.query_text or "")
        local = LocalDirectionProvider().provide(RetrievalRequest(npc_id=request.npc_id, query_text=query), {}).direction
        entities = list(direction.entity_mentions)
        locations = list(direction.location_mentions)
        calibrations: list[str] = []
        for item in local.entity_mentions:
            if item not in entities:
                entities.append(item)
                calibrations.append("explicit_entity_preserved")
        for item in local.location_mentions:
            if item not in locations:
                locations.append(item)
                calibrations.append("explicit_location_preserved")
        themes = list(direction.themes)
        constraints = list(direction.query_constraints)
        intent = direction.recall_intent
        time_scope = direction.time_scope
        if local.recall_intent == RecallIntent.LOCATE_PERSON.value:
            if intent != RecallIntent.LOCATE_PERSON.value:
                intent = RecallIntent.LOCATE_PERSON.value
                calibrations.append("direction_semantic_calibrated")
            if Theme.CURRENT_LOCATION.value not in themes:
                themes = [Theme.CURRENT_LOCATION.value]
                calibrations.append("direction_semantic_calibrated")
            if QueryConstraint.PERSON_LOCATION.value not in constraints:
                constraints.append(QueryConstraint.PERSON_LOCATION.value)
        elif local.recall_intent == RecallIntent.IDENTIFY_ENTITY.value and intent == RecallIntent.GENERAL_RECALL.value:
            intent, themes = local.recall_intent, list(local.themes)
            constraints.append(QueryConstraint.IDENTITY.value)
            calibrations.append("direction_semantic_calibrated")
        if local.time_scope == TimeScope.RECENT.value and time_scope == TimeScope.ANY.value:
            time_scope = TimeScope.RECENT.value
            if QueryConstraint.RECENT.value not in constraints:
                constraints.append(QueryConstraint.RECENT.value)
        expected = {
            RecallIntent.LOCATE_PERSON.value: QueryConstraint.PERSON_LOCATION.value,
            RecallIntent.IDENTIFY_ENTITY.value: QueryConstraint.IDENTITY.value,
            RecallIntent.COMPARE_RELATIONSHIP.value: QueryConstraint.RELATIONSHIP.value,
            RecallIntent.EXPLAIN_CAUSE.value: QueryConstraint.CAUSE.value,
            RecallIntent.RECALL_EVENT.value: QueryConstraint.PAST_EVENT.value,
        }.get(intent)
        if expected and expected not in constraints:
            constraints.append(expected)
            calibrations.append("query_constraints_calibrated")
        return RetrievalDirection(
            entity_mentions=entities, location_mentions=locations, themes=themes,
            relation_facets=direction.relation_facets, time_scope=time_scope,
            source_preferences=direction.source_preferences, recall_intent=intent,
            negative_directions=direction.negative_directions,
            retrieval_query=direction.retrieval_query, query_constraints=list(dict.fromkeys(constraints)),
        ), list(dict.fromkeys(calibrations))

    @staticmethod
    def _resolve_mentions(direction: RetrievalDirection, request: RetrievalRequest, context: dict[str, Any]) -> list[ResolvedMention]:
        """把原文 mention 映射到稳定人物或地点 ID，失败时保留语义文本。"""
        query = str(request.query_text or "")
        history = " ".join(_turn_text(turn) for turn in request.recent_turns or [])
        mentions: list[ResolvedMention] = []
        people = {**NPC_NAMES, "player": get_player_name_candidates()[0]}
        for text in [*direction.entity_mentions, *direction.location_mentions]:
            source = "query" if text and text in query else "recent_context" if text and text in history else "semantic_only"
            entity_id = ""
            entity_type = ""
            confidence = 0.25
            for candidate_id, display in people.items():
                if text in {candidate_id, display}:
                    entity_id, entity_type, confidence = candidate_id, "person", 0.95 if source == "query" else 0.65
                    break
            if not entity_id:
                for location_id, aliases in LOCATION_ALIASES.items():
                    if text == location_id or text.startswith(f"{location_id}.") or text in aliases:
                        entity_id, entity_type, confidence = location_id, "location", 0.90 if source == "query" else 0.60
                        break
            mentions.append(ResolvedMention(text, entity_id, entity_type, source, confidence))
        return mentions


class LocalDirectionProvider:
    """零 LLM 的确定性方向 provider。"""

    def provide(self, request: RetrievalRequest, context: dict[str, Any]) -> DirectionResolution:
        """从当前发言、近期对白和固定词表推断方向。"""
        query = str(request.query_text or "")
        recent = " ".join(_turn_text(turn) for turn in request.recent_turns or [])
        full_text = f"{query} {recent}"
        entities = [display for display in NPC_NAMES.values() if display in full_text]
        entities.extend(name for name in NPC_NAMES if name in full_text and name not in entities)
        locations = [location_id for location_id, aliases in LOCATION_ALIASES.items() if any(alias in full_text for alias in aliases)]
        themes = [Theme.GENERAL.value]
        relations: list[str] = []
        intent = RecallIntent.GENERAL_RECALL.value
        if any(word in query for word in ("在哪", "哪里", "位置")):
            intent, themes = RecallIntent.LOCATE_PERSON.value, [Theme.CURRENT_LOCATION.value]
        elif any(word in query for word in ("是谁", "什么人", "什么身份")):
            intent, themes = RecallIntent.IDENTIFY_ENTITY.value, [Theme.IDENTITY.value]
        elif any(word in query for word in ("为什么", "原因", "怎么会")):
            intent, themes = RecallIntent.EXPLAIN_CAUSE.value, [Theme.CAUSE.value]
        elif any(word in query for word in ("关系", "最喜欢", "熟")):
            intent, themes, relations = RecallIntent.COMPARE_RELATIONSHIP.value, [Theme.RELATIONSHIP.value], [RelationFacet.AFFINITY.value, RelationFacet.FAMILIARITY.value]
        elif any(word in query for word in ("上次", "以前", "曾经", "记得")):
            intent, themes = RecallIntent.RECALL_EVENT.value, [Theme.PAST_EVENT.value]
        time_scope = TimeScope.RECENT.value if any(word in query for word in ("最近", "刚才", "今天")) else TimeScope.PAST.value if any(word in query for word in ("上次", "以前")) else TimeScope.ANY.value
        if not entities and not locations and intent == RecallIntent.GENERAL_RECALL.value:
            themes = [Theme.GENERAL.value]
        direction = RetrievalDirection(
            entity_mentions=entities, location_mentions=locations, themes=themes,
            relation_facets=relations, time_scope=time_scope,
            source_preferences=[SourcePreference.DIRECT.value, SourcePreference.HEARD.value],
            recall_intent=intent,
            retrieval_query=query,
            query_constraints=[
                QueryConstraint.PERSON_LOCATION.value if intent == RecallIntent.LOCATE_PERSON.value else
                QueryConstraint.IDENTITY.value if intent == RecallIntent.IDENTIFY_ENTITY.value else
                QueryConstraint.CAUSE.value if intent == RecallIntent.EXPLAIN_CAUSE.value else
                QueryConstraint.RELATIONSHIP.value if intent == RecallIntent.COMPARE_RELATIONSHIP.value else
                QueryConstraint.PAST_EVENT.value if intent == RecallIntent.RECALL_EVENT.value else
                QueryConstraint.RECENT.value if time_scope == TimeScope.RECENT.value else ""
            ] if intent != RecallIntent.GENERAL_RECALL.value or time_scope == TimeScope.RECENT.value else [],
        )
        return DirectionResolution(direction=direction, source="local")


class LlmDirectionProvider:
    """只调用一次 memory_direction，并在失败时明确降级到本地 provider。"""

    def __init__(self, prompt_assembler: PromptAssembler | None = None, local_provider: LocalDirectionProvider | None = None, llm=None):
        """注入 Prompt、确定性 fallback 和可测试的 LLM client。"""
        self.prompt_assembler = prompt_assembler or PromptAssembler()
        self.local_provider = local_provider or LocalDirectionProvider()
        self.llm = llm

    def provide(self, request: RetrievalRequest, context: dict[str, Any]) -> DirectionResolution:
        """调用方向 task；失败原因使用稳定的 llm_* 值。"""
        client = self.llm
        if client is None:
            from ..dialogue import llm_client as llm_module
            client = llm_module.llm_client
        if client is None or not getattr(client, "is_available", True):
            local = self.local_provider.provide(request, context)
            return DirectionResolution(local.direction, local.mentions, "llm_unavailable", "llm_unavailable")
        prompt = self.prompt_assembler.build("memory_direction", {
            "query_text": context.get("query_text", ""),
            "conversation_summary": context.get("conversation_summary", "（暂无）"),
            "recent_turns": self._format_turns(context.get("recent_turns", [])),
            "recent_memories": "\n".join(f"- {item}" for item in context.get("recent_memories", [])) or "（暂无）",
            "location": context.get("location", "street"),
            "game_time": context.get("game_time", "未知"),
            "participant_ids": ", ".join(context.get("participant_ids", [])) or "无",
        })
        try:
            raw = client.chat(prompt, temperature=0.0)
            payload = json.loads(_strip_json_fence(raw))
            if not isinstance(payload, dict) or not payload:
                raise ValueError("empty_direction")
            direction = RetrievalDirection(
                entity_mentions=payload.get("entity_mentions", []), location_mentions=payload.get("location_mentions", []),
                themes=payload.get("themes", []), relation_facets=payload.get("relation_facets", []),
                time_scope=payload.get("time_scope", TimeScope.ANY.value), source_preferences=payload.get("source_preferences", []),
                recall_intent=payload.get("recall_intent", RecallIntent.GENERAL_RECALL.value), negative_directions=payload.get("negative_directions", []),
                retrieval_query=payload.get("retrieval_query", ""), query_constraints=payload.get("query_constraints", []),
            )
            return DirectionResolution(direction=direction, source="llm", llm_output_summary=self._safe_summary(payload))
        except json.JSONDecodeError:
            reason = "llm_invalid"
        except TimeoutError:
            reason = "llm_timeout"
        except Exception as error:
            logger.debug("memory_direction LLM failed: %s", error)
            reason = "llm_empty" if "empty_direction" in str(error) else "llm_invalid"
        local = self.local_provider.provide(request, context)
        return DirectionResolution(local.direction, local.mentions, reason, reason)

    @staticmethod
    def _format_turns(turns: list[dict[str, Any]]) -> str:
        """格式化已裁剪的近期对白。"""
        return "\n".join(f"- {item.get('speaker_id', '?')}: {item.get('text', '')}" for item in turns) or "（暂无）"

    @staticmethod
    def _safe_summary(payload: dict[str, Any]) -> str:
        """只保留结构键和值数量，不把原始隐私文本发往 Unity。"""
        return json.dumps({key: len(value) if isinstance(value, list) else value for key, value in payload.items() if key != "entity_mentions" and key != "location_mentions"}, ensure_ascii=False)[:512]
