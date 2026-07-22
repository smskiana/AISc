"""R3 v2 生产 codec 与训练模板一致性测试。"""
from __future__ import annotations
import json
import pytest
from backend.src.memory.retrieval_contracts import RetrievalRequest
from backend.src.memory.route_specialist_contract import DIRECTION_FIELDS, SpecialistContractError, SpecialistRouteCodec
from backend.training.memory_route.common import build_training_text


class _Tokenizer:
    """记录 chat template 参数的最小 tokenizer。"""
    eos_token = "<eos>"
    def apply_chat_template(self, messages, **kwargs):
        """返回稳定 JSON，供 golden 断言。"""
        assert kwargs == {"tokenize": False, "add_generation_prompt": True, "enable_thinking": False}
        return json.dumps(messages, ensure_ascii=False, separators=(",", ":"))


def _direction(**overrides: object) -> dict[str, object]:
    """构造完整合法方向。"""
    payload: dict[str, object] = {"entity_mentions": ["千早"], "location_mentions": [], "themes": ["current_location"], "relation_facets": [], "time_scope": "recent", "source_preferences": ["direct"], "recall_intent": "locate_person", "negative_directions": ["stale_location"], "retrieval_query": "千早现在在哪里", "query_constraints": ["person_location", "recent"]}
    payload.update(overrides)
    return payload


def test_runtime_and_training_use_identical_messages() -> None:
    """训练与运行时共享同一 Prompt、紧凑 JSON 和 thinking 参数。"""
    codec = SpecialistRouteCodec()
    request = RetrievalRequest(npc_id="sakura", conversation_participant_ids=["player"], query_text="千早在哪？", location_id="flower_shop.counter")
    input_payload = codec.build_input(request, {"query_text": request.query_text, "recent_turns": [], "recent_memories": []})
    prompt, full = build_training_text(_Tokenizer(), {"input": input_payload, "label": _direction()})
    assert prompt == json.dumps(codec.messages(input_payload), ensure_ascii=False, separators=(",", ":"))
    assert full.endswith("<eos>")
    assert tuple(json.loads(full[len(prompt):-5]).keys()) == DIRECTION_FIELDS


def test_codec_rejects_wrappers_unknown_fields_and_unproven_mentions() -> None:
    """Markdown、额外字段和无法证明的实体必须稳定拒绝。"""
    codec = SpecialistRouteCodec()
    request = RetrievalRequest(npc_id="sakura", query_text="千早在哪？")
    input_payload = codec.build_input(request, {"query_text": request.query_text, "recent_turns": [], "recent_memories": []})
    with pytest.raises(SpecialistContractError, match="specialist_invalid_json"):
        codec.parse_output("```json\n{}\n```", input_payload)
    with pytest.raises(SpecialistContractError, match="specialist_schema_invalid"):
        codec.parse_output(json.dumps({**_direction(), "reasoning": "x"}, ensure_ascii=False), input_payload)
    with pytest.raises(SpecialistContractError, match="specialist_semantic_rejected"):
        codec.parse_output(json.dumps(_direction(entity_mentions=["未知人物"]), ensure_ascii=False), input_payload)


def test_codec_accepts_complete_schema_v1_direction() -> None:
    """完整合法方向被转换为正式 RetrievalDirection。"""
    codec = SpecialistRouteCodec()
    request = RetrievalRequest(npc_id="sakura", query_text="千早在哪？")
    input_payload = codec.build_input(request, {"query_text": request.query_text, "recent_turns": [], "recent_memories": []})
    assert codec.parse_output(json.dumps(_direction(), ensure_ascii=False), input_payload).recall_intent == "locate_person"
