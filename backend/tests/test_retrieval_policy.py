"""三策略 policy 的默认值和严格校验测试。"""
from __future__ import annotations

import copy

import pytest

from backend.src.memory.retrieval_contracts import RetrievalStrategy
from backend.src.memory.retrieval_policy import RetrievalPolicyRegistry


def _payload_with_r3_provider() -> dict:
    """在测试 payload 中恢复冻结 R3 配置，不依赖生产注册表。"""
    import yaml
    from pathlib import Path
    payload = yaml.safe_load((Path(__file__).parents[1] / "config" / "memory_retrieval.yaml").read_text(encoding="utf-8"))
    payload["direction_providers"]["providers"]["r3_v2"] = {
        "kind": "subprocess_specialist",
        "model_id": "Qwen/Qwen3-0.6B",
        "revision": "c1899de289a04d12100db370d81485cdf75e47ca",
        "adapter_id": "route-lora-r3-v2-approved-480",
        "adapter_sha256": "cd2676f7f64f28a351fb35b2d2d76fa01b30662a509bf7bbddcced6f9cf92b8d",
        "python_env": "MEMORY_ROUTE_PYTHON",
        "adapter_path_env": "MEMORY_ROUTE_R3_V2_ADAPTER",
        "hf_home_env": "HF_HOME",
        "timeout_ms": 16000,
        "max_new_tokens": 384,
        "restart_cooldown_ms": 5000,
    }
    return payload


def test_default_modes_and_nightly_budget() -> None:
    """默认策略符合执行案，夜间本地预算高于玩家。"""
    registry = RetrievalPolicyRegistry()
    assert registry.version == 2
    assert registry.direction_providers.default_chain == ("local",)
    assert registry.get("player_dialogue").direction_chain == ("local",)
    assert registry.get("npc_dialogue").direction_chain == ("local",)
    assert registry.get("nightly_impression").direction_chain == ("local",)
    assert set(registry.direction_providers.providers) == {"general_llm", "local"}
    assert registry.get("player_dialogue").strategy == RetrievalStrategy.LOCAL_ONLY
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


def test_provider_registry_rejects_paths_unknown_ids_and_invalid_chains() -> None:
    """provider 配置只接受环境变量名、已注册成员和 local 终点。"""
    import yaml
    from pathlib import Path
    payload = _payload_with_r3_provider()
    invalid = copy.deepcopy(payload)
    invalid["direction_providers"]["providers"]["r3_v2"]["python_env"] = "C:/python.exe"
    with pytest.raises(ValueError, match="must_be_env_name"):
        RetrievalPolicyRegistry(payload=invalid)
    invalid = copy.deepcopy(payload)
    invalid["modes"]["player_dialogue"]["direction_chain"] = ["missing", "local"]
    with pytest.raises(ValueError, match="direction_chain_invalid"):
        RetrievalPolicyRegistry(payload=invalid)


def test_yaml_loader_rejects_duplicate_mapping_keys(tmp_path) -> None:
    """重复 YAML key 必须在覆盖配置前使启动失败。"""
    from pathlib import Path
    source = (Path(__file__).parents[1] / "config" / "memory_retrieval.yaml").read_text(encoding="utf-8")
    path = tmp_path / "duplicate.yaml"
    path.write_text(source.replace("version: 2", "version: 2\nversion: 2", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate key"):
        RetrievalPolicyRegistry(config_path=path)
