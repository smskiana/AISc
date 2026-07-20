"""方向契约解析、非法枚举和 LLM 降级测试。"""
from __future__ import annotations

from backend.src.memory.retrieval_contracts import RetrievalRequest
from backend.src.memory.retrieval_direction import DirectionResolver, LocalDirectionProvider, LlmDirectionProvider


class FakeLlm:
    """提供可重复的结构化方向输出。"""

    is_available = True

    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def chat(self, messages, **kwargs):
        """记录一次调用并返回固定 JSON。"""
        self.calls += 1
        return self.response


def test_local_direction_resolves_person_and_location_intent() -> None:
    """本地方向能识别人物 mention 和定位意图。"""
    request = RetrievalRequest(npc_id="kujo", conversation_participant_ids=["player"], query_text="千早在哪？")
    resolver = DirectionResolver()
    result = resolver.resolve(request, {}, LocalDirectionProvider())
    assert result.source == "local"
    assert result.direction.recall_intent == "locate_person"
    assert result.mentions[0].entity_id == "chihaya"


def test_invalid_llm_enum_is_cleaned_and_calls_once() -> None:
    """非法枚举会被丢弃并记录，而不是进入 scorer。"""
    llm = FakeLlm('{"entity_mentions":["千早"],"themes":["not_allowed"],"time_scope":"future","recall_intent":"general_recall"}')
    request = RetrievalRequest(npc_id="kujo", query_text="千早是谁？")
    result = DirectionResolver().resolve(request, {}, LlmDirectionProvider(llm=llm))
    assert llm.calls == 1
    assert result.direction.themes == ["identity"]
    assert "direction_semantic_calibrated" in result.calibrations
    assert result.direction.time_scope == "any"
    assert result.validation_errors


def test_invalid_llm_field_shapes_are_cleaned_without_crashing() -> None:
    """数组标量、对象枚举和文本非数组应稳定降级并保留错误证据。"""
    llm = FakeLlm(
        '{"entity_mentions":"千早","location_mentions":{},"themes":[{}],'
        '"time_scope":["recent"],"recall_intent":["locate_person"]}'
    )
    request = RetrievalRequest(npc_id="kujo", query_text="发生了什么？")

    result = DirectionResolver().resolve(request, {}, LlmDirectionProvider(llm=llm))

    assert result.direction.entity_mentions == []
    assert result.direction.location_mentions == []
    assert result.direction.themes == ["general"]
    assert result.direction.time_scope == "any"
    assert result.direction.recall_intent == "general_recall"
    assert "entity_mentions_not_array" in result.validation_errors
    assert "location_mentions_not_array" in result.validation_errors
    assert any(error.startswith("invalid_time_scope:") for error in result.validation_errors)
    assert any(error.startswith("invalid_recall_intent:") for error in result.validation_errors)


def test_unknown_location_text_is_not_bound_to_first_person() -> None:
    """问题中的未知地点文本不得仅因出现在 query 中就绑定到人物。"""
    llm = FakeLlm(
        '{"entity_mentions":["千早"],"location_mentions":["小镇","flower_shop.counter"],'
        '"themes":["promise"],"time_scope":"any","recall_intent":"general_recall"}'
    )
    request = RetrievalRequest(npc_id="sakura", query_text="千早是不是答应离开小镇？")

    result = DirectionResolver().resolve(request, {}, LlmDirectionProvider(llm=llm))
    mentions = {item.text: item for item in result.mentions}

    assert mentions["千早"].entity_id == "chihaya"
    assert mentions["小镇"].entity_id == ""
    assert mentions["小镇"].entity_type == ""
    assert mentions["flower_shop.counter"].entity_id == "flower_shop"
    assert mentions["flower_shop.counter"].entity_type == "location"


def test_unavailable_llm_uses_explicit_local_failure_source() -> None:
    """LLM 不可用时保持可检索，并区分 llm_unavailable。"""
    request = RetrievalRequest(npc_id="kujo", query_text="千早是谁？")
    result = DirectionResolver().resolve(request, {}, LlmDirectionProvider(llm=None))
    assert result.source == "llm_unavailable"
    assert result.failure_reason == "llm_unavailable"
    assert result.direction.recall_intent == "identify_entity"
