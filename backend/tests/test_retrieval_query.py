"""检索想法校验、近期对白选择和单次 query 预算测试。"""
from __future__ import annotations

from backend.src.memory.retrieval_contracts import DirectionResolution, RetrievalDirection, RetrievalRequest
from backend.src.memory.retrieval_policy import RetrievalPolicyRegistry
from backend.src.memory.retrieval_query import RetrievalQueryPlanner


def _policy(mode: str = "player_dialogue"):
    """读取真实配置中的已校验策略。"""
    return RetrievalPolicyRegistry().get(mode)


def test_query_plan_keeps_original_question_and_excludes_scene_noise() -> None:
    """embedding query 只由问题、检索想法和一条相关对白组成。"""
    request = RetrievalRequest(
        npc_id="kujo", query_text="你知道千早在哪里吗，我在找她",
        location_id="flower_shop.counter", conversation_summary="玩家在喫茶店长大",
        recent_turns=[{"text": "九条说千早可能去过书店。"}],
    )
    resolution = DirectionResolution(RetrievalDirection(
        entity_mentions=["千早"], retrieval_query="查找千早的已知位置记忆", query_constraints=["person_location"],
    ), source="llm")
    plan = RetrievalQueryPlanner().plan(request, resolution, _policy())
    assert "当前问题：你知道千早在哪里吗，我在找她" in plan.embedding_query
    assert "检索想法：查找千早的已知位置记忆" in plan.embedding_query
    assert "相关近期对白：九条说千早可能去过书店。" in plan.embedding_query
    assert "flower_shop.counter" not in plan.embedding_query
    assert "喫茶店长大" not in plan.embedding_query


def test_query_plan_rejects_new_entity_and_time_claims() -> None:
    """LLM 检索想法不能借 query 引入原问题没有的稳定事实。"""
    request = RetrievalRequest(npc_id="kujo", query_text="千早在哪里？")
    planner = RetrievalQueryPlanner()
    entity_plan = planner.plan(request, DirectionResolution(RetrievalDirection(retrieval_query="和叶说千早第3天在花店", entity_mentions=["千早"]), source="llm"), _policy())
    assert entity_plan.retrieval_query == request.query_text
    assert entity_plan.fallback_reason == "retrieval_query_entity_mismatch"
    time_plan = planner.plan(request, DirectionResolution(RetrievalDirection(retrieval_query="千早第3天在哪里", entity_mentions=["千早"]), source="llm"), _policy())
    assert time_plan.fallback_reason == "retrieval_query_fact_risk"


def test_query_plan_only_uses_recent_turn_for_overlap_or_pronoun() -> None:
    """明确问题不带入无关对白，指代问题才选择可解析实体的最近一条。"""
    planner = RetrievalQueryPlanner()
    resolution = DirectionResolution(RetrievalDirection(retrieval_query="喫茶店近况"), source="local")
    direct = planner.plan(RetrievalRequest(npc_id="kujo", query_text="喫茶店最近怎么样？", recent_turns=[{"text": "千早昨天去过书店。"}]), resolution, _policy())
    assert direct.selected_recent_turn == ""
    pronoun = planner.plan(RetrievalRequest(npc_id="kujo", query_text="她最近怎么样？", recent_turns=[{"text": "千早昨天去过书店。"}]), resolution, _policy())
    assert pronoun.selected_recent_turn == "千早昨天去过书店。"
    assert pronoun.selection_reason == "pronoun_resolved_entity"


def test_query_plan_preserves_over_budget_original_question() -> None:
    """当前问题自身超过总预算时不得从中间截断。"""
    request = RetrievalRequest(npc_id="kujo", query_text="千早" * 400)
    plan = RetrievalQueryPlanner().plan(request, DirectionResolution(RetrievalDirection(retrieval_query="千早"), source="local"), _policy())
    assert plan.embedding_query == request.query_text
    assert plan.original_query_exceeds_budget
