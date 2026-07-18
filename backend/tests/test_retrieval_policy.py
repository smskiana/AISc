"""三策略 policy 的默认值和严格校验测试。"""
from __future__ import annotations

import copy

import pytest

from backend.src.memory.retrieval_contracts import RetrievalStrategy
from backend.src.memory.retrieval_policy import RetrievalPolicyRegistry


def test_default_modes_and_nightly_budget() -> None:
    """默认策略符合执行案，夜间本地预算高于玩家。"""
    registry = RetrievalPolicyRegistry()
    assert registry.get("player_dialogue").strategy == RetrievalStrategy.LLM_GUIDED_LOCAL
    assert registry.get("npc_dialogue").strategy == RetrievalStrategy.LOCAL_ONLY
    assert registry.get("nightly_impression").strategy == RetrievalStrategy.LOCAL_ONLY
    assert registry.get("nightly_impression").local_search.budget.max_depth > registry.get("player_dialogue").local_search.budget.max_depth
    assert registry.get("nightly_impression").context.max_direction_context_chars > registry.get("player_dialogue").context.max_direction_context_chars
    assert [registry.get(mode).local_search.budget.max_depth for mode in ("player_dialogue", "npc_dialogue", "nightly_impression")] == [7, 5, 8]
    nightly = registry.get("nightly_impression").local_search.budget
    assert (nightly.beam_width, nightly.max_neighbors_per_node, nightly.max_expanded_edges) == (12, 16, 48)
    assert [registry.get(mode).llm_route.max_llm_route_calls for mode in ("player_dialogue", "npc_dialogue", "nightly_impression")] == [7, 5, 7]


def test_unknown_strategy_and_cross_field_conflict_fail() -> None:
    """未知策略和 selected_edges 超过候选数不能静默降级。"""
    # 通过真实配置复制完整嵌套字段，避免测试绕过完整字段校验。
    import yaml
    from pathlib import Path
    payload = yaml.safe_load((Path(__file__).parents[1] / "config" / "memory_retrieval.yaml").read_text(encoding="utf-8"))
    invalid = copy.deepcopy(payload)
    invalid["modes"]["player_dialogue"]["strategy"] = "unknown"
    with pytest.raises(ValueError, match="unknown_strategy"):
        RetrievalPolicyRegistry(payload=invalid)
    invalid = copy.deepcopy(payload)
    invalid["modes"]["player_dialogue"]["llm_route"]["selected_edges_per_hop"] = 9
    with pytest.raises(ValueError, match="selected_edges"):
        RetrievalPolicyRegistry(payload=invalid)
    invalid = copy.deepcopy(payload)
    invalid["modes"]["player_dialogue"]["final_scoring"]["node_type_prior"] = 0.06
    invalid["modes"]["player_dialogue"]["final_scoring"]["importance"] = 0.07
    with pytest.raises(ValueError, match="node_type_prior"):
        RetrievalPolicyRegistry(payload=invalid)
