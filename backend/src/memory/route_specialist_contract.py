"""R3 v2 记忆路由专项模型的生产侧输入、Prompt 与输出契约。"""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from ..dialogue.player_name import get_player_name_candidates
from .retrieval_contracts import NegativeDirection, QueryConstraint, RecallIntent, RelationFacet, RetrievalDirection, RetrievalRequest, SourcePreference, Theme, TimeScope

DIRECTION_FIELDS = ("entity_mentions", "location_mentions", "themes", "relation_facets", "time_scope", "source_preferences", "recall_intent", "negative_directions", "retrieval_query", "query_constraints")
INPUT_FIELDS = ("schema_version", "npc_id", "query_text", "conversation_summary", "recent_turns", "recent_memories", "location_id", "location_display_text", "game_time_snapshot", "participant_ids", "known_entity_aliases", "mode")
SYSTEM_PROMPT = (
    "你是记忆检索方向解析器。只输出一个 JSON 对象，不输出推理过程、回答、节点 ID 或边 ID。"
    "字段必须完整且只能是：entity_mentions:string[]，location_mentions:string[]，"
    "themes:[identity|current_location|recent_activity|relationship|cause|past_event|emotion|object|promise|general]，"
    "relation_facets:[familiarity|affinity|occupation|shared_event|impression_basis|knowledge_source]，"
    "time_scope:current|recent|past|any，source_preferences:[direct|heard|inferred]，"
    "recall_intent:locate_person|identify_entity|explain_cause|compare_relationship|recall_event|continue_reference|general_recall，"
    "negative_directions:[unrelated_player_background|unrelated_private_memory|stale_location|unrelated_person]，"
    "retrieval_query:string，query_constraints:[person_location|identity|relationship|cause|past_event|recent]。"
    "不得引入输入中不存在的人物、地点、时间或事件。"
)
NPC_ALIASES = {"sakura": ("鹿岛樱", "小樱"), "chihaya": ("千早",), "kazuha": ("和叶",), "tatsunosuke": ("龙之介",), "kujo": ("九条莲", "九条")}
LOCATION_ALIASES = {"player_cafe": ("喫茶店", "咖啡店"), "flower_shop": ("花店",), "bakery": ("面包店", "烘焙店"), "bookstore": ("旧书店", "书店"), "wagashi": ("和果子店",), "police_box": ("派出所",), "street": ("商店街", "樱桥通"), "park": ("小公园",), "riverside": ("河边", "樱花道")}
_ENUMS = {"themes": {item.value for item in Theme}, "relation_facets": {item.value for item in RelationFacet}, "time_scope": {item.value for item in TimeScope}, "source_preferences": {item.value for item in SourcePreference}, "recall_intent": {item.value for item in RecallIntent}, "negative_directions": {item.value for item in NegativeDirection}, "query_constraints": {item.value for item in QueryConstraint}}
_ARRAY_FIELDS = set(DIRECTION_FIELDS) - {"time_scope", "recall_intent", "retrieval_query"}
_FORBIDDEN_ID = re.compile(r"(?:^|[^a-z])(node|edge)[_-]?id(?:$|[^a-z])", re.IGNORECASE)


class SpecialistContractError(ValueError):
    """携带稳定失败原因的专项模型契约异常。"""
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class SpecialistRouteCodec:
    """把正式检索请求映射到 schema v1，并严格解析模型方向。"""
    schema_version = 1

    def build_input(self, request: RetrievalRequest, context: dict[str, Any]) -> dict[str, Any]:
        """构造与冻结训练数据一致的紧凑 schema v1 input。"""
        location_id = str(request.location_id or context.get("location") or "street")
        location_root = location_id.split(".", 1)[0]
        location_aliases = LOCATION_ALIASES.get(location_root, ())
        participants = tuple(dict.fromkeys([request.npc_id, *request.conversation_participant_ids]))
        searchable = " ".join([str(request.query_text or ""), str(context.get("conversation_summary", "")), *(str(item.get("text", "")) for item in context.get("recent_turns", []) if isinstance(item, dict)), *(str(item) for item in context.get("recent_memories", []))])
        aliases: list[str] = []
        for entity_id, names in NPC_ALIASES.items():
            if entity_id in participants or entity_id in searchable or any(name in searchable for name in names):
                aliases.extend((entity_id, *names))
        if "player" in participants:
            aliases.extend(("player", *get_player_name_candidates()))
        if location_root in searchable or location_id in searchable or any(name in searchable for name in location_aliases):
            aliases.extend((location_root, location_id, *location_aliases))
        return {"schema_version": 1, "npc_id": request.npc_id, "query_text": str(context.get("query_text", request.query_text or "")), "conversation_summary": str(context.get("conversation_summary", "")), "recent_turns": list(context.get("recent_turns", [])), "recent_memories": [str(item) for item in context.get("recent_memories", [])], "location_id": location_id, "location_display_text": location_aliases[0] if location_aliases else location_root, "game_time_snapshot": str(context.get("game_time", request.game_time or "未知")), "participant_ids": list(request.conversation_participant_ids), "known_entity_aliases": list(dict.fromkeys(item for item in aliases if item)), "mode": request.mode}

    @staticmethod
    def messages(input_payload: dict[str, Any]) -> list[dict[str, str]]:
        """生成训练与运行时共用的唯一 chat messages。"""
        if set(input_payload) != set(INPUT_FIELDS) or input_payload.get("schema_version") != 1:
            raise SpecialistContractError("specialist_schema_invalid")
        compact = json.dumps(input_payload, ensure_ascii=False, separators=(",", ":"))
        return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": compact}]

    def parse_output(self, raw: str, input_payload: dict[str, Any]) -> RetrievalDirection:
        """严格解析单一 JSON object，并拒绝结构或语义越权。"""
        text = str(raw or "").strip()
        if not text or text.startswith("```"):
            raise SpecialistContractError("specialist_invalid_json")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise SpecialistContractError("specialist_invalid_json") from error
        if not isinstance(payload, dict) or set(payload) != set(DIRECTION_FIELDS):
            raise SpecialistContractError("specialist_schema_invalid")
        for field in _ARRAY_FIELDS:
            value = payload[field]
            if not isinstance(value, list) or len(value) > 8 or any(not isinstance(item, str) or len(item) > 160 for item in value):
                raise SpecialistContractError("specialist_schema_invalid")
        for field in ("time_scope", "recall_intent", "retrieval_query"):
            if not isinstance(payload[field], str) or len(payload[field]) > 320:
                raise SpecialistContractError("specialist_schema_invalid")
        for field, allowed in _ENUMS.items():
            values = [payload[field]] if isinstance(payload[field], str) else payload[field]
            if any(item not in allowed for item in values):
                raise SpecialistContractError("specialist_schema_invalid")
        if any(_FORBIDDEN_ID.search(item) for field in DIRECTION_FIELDS for item in ([payload[field]] if isinstance(payload[field], str) else payload[field])):
            raise SpecialistContractError("specialist_schema_invalid")
        self._validate_mentions(payload, input_payload)
        return RetrievalDirection(**{field: payload[field] for field in DIRECTION_FIELDS})

    @staticmethod
    def _validate_mentions(payload: dict[str, Any], input_payload: dict[str, Any]) -> None:
        """确保人物和地点 mention 均能由本次最小输入证明。"""
        evidence = json.dumps(input_payload, ensure_ascii=False, separators=(",", ":"))
        stable = set(input_payload.get("known_entity_aliases", [])) | set(input_payload.get("participant_ids", []))
        stable.update((str(input_payload.get("npc_id", "")), str(input_payload.get("location_id", "")), str(input_payload.get("location_display_text", ""))))
        if any(mention not in stable and mention not in evidence for mention in [*payload["entity_mentions"], *payload["location_mentions"]]):
            raise SpecialistContractError("specialist_semantic_rejected")


def direction_from_payload(payload: dict[str, Any]) -> RetrievalDirection:
    """只从正式白名单字段构建 RetrievalDirection。"""
    return RetrievalDirection(**{field: payload[field] for field in DIRECTION_FIELDS if field in payload})


def direction_to_payload(direction: RetrievalDirection) -> dict[str, Any]:
    """把正式 RetrievalDirection 转为稳定方向字段映射。"""
    values = asdict(direction)
    return {field: values[field] for field in DIRECTION_FIELDS}
