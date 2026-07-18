"""离线评估三业务模式 × 三策略的快速入口，不连接真实 LLM 或正式数据。"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.memory.retrieval import RetrievalEngine
from backend.src.memory.retrieval_contracts import RetrievalRequest
from backend.src.memory.retrieval_policy import RetrievalPolicyRegistry


class EvaluationDatabase:
    """提供一个可重复的三跳竞争图。"""

    def __init__(self):
        self.logs = []

    def get_nodes_by_npc(self, npc_id):
        """返回固定起点和深层证据节点。"""
        return [{"id": item} for item in ("self", "player", "chihaya", "event_1", "event_2")]

    def fetchone(self, query, params=()):
        """返回空状态，评估只关注路由行为。"""
        return {}

    def fetchall(self, query, params=()):
        """返回空短期记忆。"""
        return []

    def get_directional_neighbors(self, node_id, limit=20):
        """返回人物、关系和背景竞争边。"""
        graph = {
            "self": [
                {"id": "edge_person", "neighbor_id": "chihaya", "directional_clarity": 0.78, "type": "relationship", "direction": "ab", "target_importance": 0.9},
                {"id": "edge_background", "neighbor_id": "event_1", "directional_clarity": 0.98, "type": "involved", "direction": "ba", "target_importance": 0.8},
            ],
            "player": [{"id": "edge_player", "neighbor_id": "event_2", "directional_clarity": 0.95, "type": "involved", "direction": "ba", "target_importance": 0.9}],
            "chihaya": [], "event_1": [{"id": "edge_deep", "neighbor_id": "event_2", "directional_clarity": 0.7, "type": "mentioned", "direction": "ab", "target_importance": 0.7}], "event_2": [],
        }
        return graph.get(node_id, [])[:limit]

    def insert_retrieval_log(self, row):
        """收集旧表兼容日志。"""
        self.logs.append(row)


class EvaluationVectorStore:
    """提供固定节点正文和一次向量命中。"""

    def get_batch(self, npc_id, node_ids):
        """返回节点类型和语义内容。"""
        nodes = {
            "self": {"node_id": "self", "type": "self", "value": "我", "importance": 1.0},
            "player": {"node_id": "player", "type": "person", "value": "小李", "importance": 0.5},
            "chihaya": {"node_id": "chihaya", "type": "person", "value": "千早", "importance": 0.9},
            "event_1": {"node_id": "event_1", "type": "event", "value": "商店街听说小李回来了", "importance": 0.8},
            "event_2": {"node_id": "event_2", "type": "event", "value": "千早最近在面包店附近", "importance": 0.8},
        }
        return [nodes[node_id] for node_id in node_ids if node_id in nodes]

    def search(self, npc_id, vector, top_k=5, **kwargs):
        """返回不改变起点的语义锚点。"""
        return [{"node_id": "event_2", "archived": 0}][:top_k]


class EvaluationLlm:
    """根据 task 文本返回方向或候选选择。"""

    is_available = True

    def __init__(self):
        self.calls = 0

    def chat(self, messages, **kwargs):
        """记录调用并返回最小合法 JSON。"""
        self.calls += 1
        content = messages[0]["content"]
        if "受控检索方向" in content:
            return '{"entity_mentions":["千早"],"location_mentions":[],"themes":["identity"],"relation_facets":["affinity"],"time_scope":"any","source_preferences":["direct"],"recall_intent":"identify_entity","negative_directions":[],"retrieval_query":"查找千早的身份与位置相关记忆","query_constraints":["identity"]}'
        return '{"selected":[0]}'


def run() -> list[dict]:
    """执行九种组合并返回可审计的最小指标。"""
    config_path = Path(__file__).parents[1] / "config" / "memory_retrieval.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    results = []
    for mode in ("player_dialogue", "npc_dialogue", "nightly_impression"):
        for strategy in ("local_only", "llm_guided_local", "llm_full_route"):
            variant = copy.deepcopy(payload)
            variant["modes"][mode]["strategy"] = strategy
            llm = EvaluationLlm()
            engine = RetrievalEngine(EvaluationDatabase(), EvaluationVectorStore(), policy_registry=RetrievalPolicyRegistry(payload=variant), llm=llm)
            result = engine.retrieve(RetrievalRequest(npc_id="kujo", conversation_participant_ids=["player"], query_text="千早在哪？", location_id="street.crossroad", game_time="第1天 10:00", mode=mode))
            results.append({
                "mode": mode, "strategy": strategy, "llm_calls": llm.calls,
                "retrieved_node_ids": result.retrieved_node_ids,
                "selected_edge_ids": result.selected_edge_ids,
                "stop_reason": result.diagnostics.get("stop_reason"),
                "failure_reason": result.diagnostics.get("failure_reason"),
                "vector_queries": result.diagnostics.get("vector_query_count", 0),
                "retrieval_query_source": result.diagnostics.get("retrieval_query_source", ""),
                "final_score_components": [item.get("score_components", []) for item in result.diagnostics.get("final_entries", [])],
                "evicted_entries": result.diagnostics.get("evicted_entries", []),
                "final_entry_chars": result.diagnostics.get("final_context_chars", 0),
            })
    return results


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
