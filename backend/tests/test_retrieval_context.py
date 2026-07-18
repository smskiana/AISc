"""最终原子记忆条目选择、字符预算和向量距离转换测试。"""
from __future__ import annotations

from backend.src.database.lancedb_client import LanceDBClient
from backend.src.memory.retrieval_context import RetrievalContextAssembler
from backend.src.memory.retrieval_contracts import RetrievalQueryPlan, VectorSearchHit
from backend.src.memory.retrieval_policy import RetrievalPolicyRegistry


def test_entity_memory_beats_unrelated_high_importance_event() -> None:
    """人物节点不占保底槽，但明确实体相关性不能被 event 类型先验单独挤掉。"""
    policy = RetrievalPolicyRegistry().get("player_dialogue")
    assembly = RetrievalContextAssembler().assemble([
        {"node_id": "chihaya", "type": "person", "value": "千早", "importance": 0.7, "created_day": 1, "local_score": 0.7},
        {"node_id": "event", "type": "event", "value": "无关的商店街庆典", "importance": 1.0, "created_day": 1, "local_score": 0.9},
    ], RetrievalQueryPlan("千早在哪里？", "千早在哪里？", "local", [], ["千早"]), [], "第1天", policy)
    assert assembly.entries[0].node_id == "chihaya"
    assert "千早" in assembly.context_text


def test_person_entries_render_neutrally_and_never_split_under_budget() -> None:
    """person 条目进入 Prompt 时保持中性；空间不足整条淘汰。"""
    policy = RetrievalPolicyRegistry().get("npc_dialogue")
    tiny_policy = policy.__class__(policy.mode, policy.strategy, policy.context.__class__(**{**policy.context.__dict__, "final_context_max_chars": 64}), policy.local_search, policy.llm_route, policy.scoring, policy.final_scoring, policy.version)
    assembly = RetrievalContextAssembler().assemble([
        {"node_id": "person", "type": "person", "value": "千早", "importance": 0.5, "created_day": 1, "local_score": 0.8},
        {"node_id": "long", "type": "event", "value": "很长的记忆" * 30, "importance": 1.0, "created_day": 1, "local_score": 1.0},
    ], RetrievalQueryPlan("千早是谁？", "千早是谁？", "local", [], ["千早"]), [VectorSearchHit("person", 1, 0.9)], "第1天", tiny_policy)
    assert assembly.entries[0].rendered_text.endswith("千早")
    assert any(item["reason"] == "entry_exceeds_context_budget" for item in assembly.evicted_entries)
    assert "很长的记忆" not in assembly.context_text


def test_normalized_lancedb_distance_is_explicit_and_bounded() -> None:
    """归一化向量的平方 L2 转换稳定落在 0..1。"""
    assert LanceDBClient.normalized_similarity(0.0) == 1.0
    assert LanceDBClient.normalized_similarity(2.0) == 0.5
    assert LanceDBClient.normalized_similarity(4.0) == 0.0


def test_recency_reads_game_day_without_merging_clock_digits() -> None:
    """第1天 10:00 应按第 1 天而不是 11000 天计算时效。"""
    assert RetrievalContextAssembler._recency(1, "第1天 10:00") == 1.0
