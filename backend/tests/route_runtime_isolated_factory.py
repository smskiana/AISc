"""R3 v2 运行时验收专用的脱敏隔离 SQLite/LanceDB engine factory。"""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
from typing import Any

import yaml

from backend.src.database.lancedb_client import LanceDBClient
from backend.src.database.sqlite_client import SQLiteClient
from backend.src.memory.retrieval import RetrievalEngine
from backend.src.memory.retrieval_policy import RetrievalPolicyRegistry
from backend.src.memory.route_specialist_provider import DirectionProviderRuntime


class _DeterministicGeneralLlm:
    """只为隔离 factory 提供稳定通用方向，不访问外部 API。"""
    is_available = True

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """根据脱敏固定问题返回正式通用 provider 可解析的方向。"""
        content = json.dumps(messages, ensure_ascii=False)
        locate = "在哪" in content or "哪里" in content
        payload = {
            "entity_mentions": ["千早"], "location_mentions": [],
            "themes": ["current_location" if locate else "identity"], "relation_facets": [],
            "time_scope": "current" if locate else "any", "source_preferences": ["direct"],
            "recall_intent": "locate_person" if locate else "identify_entity", "negative_directions": [],
            "retrieval_query": "千早当前位置" if locate else "千早身份",
            "query_constraints": ["person_location"] if locate else ["identity"],
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _provider_payload(provider_id: str) -> dict[str, Any]:
    """从正式配置复制预算，只收窄本次隔离评估的 provider 注册表。"""
    config_path = Path(__file__).parents[1] / "config" / "memory_retrieval.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    providers = payload["direction_providers"]["providers"]
    if provider_id == "r3_v2":
        providers["r3_v2"] = {
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
    chains = {"r3_v2": ["r3_v2", "local"], "general_llm": ["general_llm", "local"], "local": ["local"]}
    required = set(chains[provider_id])
    payload["direction_providers"]["providers"] = {key: copy.deepcopy(value) for key, value in providers.items() if key in required}
    payload["direction_providers"]["default_chain"] = list(chains[provider_id])
    payload["modes"]["player_dialogue"]["strategy"] = "local_only" if provider_id == "local" else "llm_guided_local"
    payload["modes"]["player_dialogue"]["direction_chain"] = list(chains[provider_id])
    return payload


def _seed_graph(sqlite: SQLiteClient, vectors: LanceDBClient) -> None:
    """写入固定起点、允许记忆和另一个 NPC 的禁止私有记忆。"""
    nodes = [
        {"id": "iso_sakura_self", "subject_id": "sakura", "type": "self", "value": "我"},
        {"id": "iso_sakura_player", "subject_id": "sakura", "type": "person", "value": "小李"},
        {"id": "iso_sakura_chihaya", "subject_id": "sakura", "type": "person", "value": "千早"},
        {"id": "iso_chihaya_location", "subject_id": "sakura", "type": "place", "value": "千早今天在花店"},
        {"id": "iso_kujo_private", "subject_id": "kujo", "type": "event", "value": "九条的私有记忆"},
    ]
    for node in nodes:
        sqlite.insert_node(node)
    sqlite.insert_edge({"id": "iso_edge_knows_chihaya", "node_a": "iso_sakura_self", "node_b": "iso_sakura_chihaya", "type": "relationship", "clarity_ab": 0.95, "clarity_ba": 0.9, "target_importance": 0.95})
    sqlite.insert_edge({"id": "iso_edge_chihaya_location", "node_a": "iso_sakura_chihaya", "node_b": "iso_chihaya_location", "type": "located_at", "clarity_ab": 0.96, "clarity_ba": 0.9, "target_importance": 0.95})
    vector = [0.0] * 512
    for npc_id in ("sakura", "kujo"):
        vectors.upsert_nodes(npc_id, [{"node_id": node["id"], "vector": vector, "type": node["type"], "value": node["value"], "importance": 0.95, "created_day": 4, "archived": 0} for node in nodes if node["subject_id"] == npc_id])


def create_engine(provider_id: str) -> RetrievalEngine:
    """创建只连接临时 SQLite/LanceDB 的正式 RetrievalEngine。"""
    if provider_id not in {"r3_v2", "general_llm", "local"}:
        raise ValueError("unsupported_direction_provider")
    temp_dir = tempfile.TemporaryDirectory(prefix="aisc-route-runtime-")
    root = Path(temp_dir.name)
    sqlite = SQLiteClient(str(root / "game.db"))
    vectors = LanceDBClient(str(root / "lancedb"), ["sakura", "kujo"])
    _seed_graph(sqlite, vectors)
    registry = RetrievalPolicyRegistry(payload=_provider_payload(provider_id))
    llm = _DeterministicGeneralLlm() if provider_id == "general_llm" else None
    runtime = DirectionProviderRuntime(registry, llm=llm)
    engine = RetrievalEngine(sqlite, vectors, policy_registry=registry, llm=llm, direction_provider_runtime=runtime)
    engine._route_runtime_isolation = temp_dir
    return engine


create_engine.aisc_isolated_retrieval_factory = True
