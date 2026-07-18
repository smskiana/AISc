"""固定起点、本地深搜预算和权限过滤测试。"""
from __future__ import annotations

from backend.src.memory.deep_retrieval import DirectedDeepRetriever
from backend.src.memory.retrieval_contracts import (
    LlmGraphSearchRequest,
    LlmRoutePolicy,
    DeepSearchRequest,
    LocalSearchPolicy,
    RetrievalDirection,
    SearchBudget,
)
from backend.src.memory.llm_graph_retrieval import LlmGraphRetriever


class Graph:
    """提供超过两跳的最小固定图。"""

    def get_directional_neighbors(self, node_id, limit=20):
        """返回一条深路径和一个被归档的竞争边。"""
        graph = {
            "self": [{"id": "e1", "neighbor_id": "a", "directional_clarity": 0.8, "type": "relationship", "direction": "ab", "target_importance": 0.7}],
            "a": [{"id": "e2", "neighbor_id": "b", "directional_clarity": 0.8, "type": "involved", "direction": "ab", "target_importance": 0.7}],
            "b": [{"id": "e3", "neighbor_id": "target", "directional_clarity": 0.9, "type": "mentioned", "direction": "ab", "target_importance": 0.9}, {"id": "blocked", "neighbor_id": "secret", "directional_clarity": 1.0, "type": "involved", "direction": "ab", "target_importance": 1.0, "archived": 1}],
            "target": [],
        }
        return graph.get(node_id, [])[:limit]


class Nodes:
    """返回路径节点的稳定内容。"""

    def get_batch(self, npc_id, node_ids):
        """返回节点摘要和目标 mention。"""
        values = {"self": ("self", "我"), "a": ("event", "关系线索"), "b": ("event", "一件过去的事"), "target": ("person", "目标")}
        return [{"node_id": node_id, "type": values[node_id][0], "value": values[node_id][1], "importance": 0.8} for node_id in node_ids if node_id in values]


def test_deep_search_reaches_target_without_making_anchor_a_start() -> None:
    """目标锚点只用于排序，真实路径必须从 self 出发。"""
    policy = LocalSearchPolicy(SearchBudget(4, 2, 4, 20, 2, 8, 0.0, 0.0))
    outcome = DirectedDeepRetriever(Graph(), Nodes()).search(DeepSearchRequest(
        npc_id="kujo", target_id="player", start_node_ids=["self"], target_start_id=None,
        direction=RetrievalDirection(entity_mentions=["目标"], themes=["identity"]),
        policy=policy, vector_anchor_ids=["target"],
    ))
    assert outcome.node_ids[-1] == "target"
    assert "target" not in [item for item in ["self"]]
    assert [item.edge_id for item in outcome.path_evidence] == ["e1", "e2", "e3"]
    assert outcome.counters["filtered_archived"] == 1


def test_extended_local_and_llm_depth_reach_newly_allowed_path() -> None:
    """深度上调后，本地和完全 LLM 路由均能到达旧上限外的第 5 层证据。"""
    class ChainGraph:
        """提供只有一条可达五层路径的固定图。"""

        def get_directional_neighbors(self, node_id, limit=10):
            index = int(node_id[1:]) if node_id.startswith("n") else 0
            return [] if index >= 5 else [{"id": f"e{index}", "neighbor_id": f"n{index + 1}", "directional_clarity": 0.9, "type": "mentioned", "direction": "ab", "target_importance": 0.8}]

    class ChainNodes:
        """为固定图提供稳定节点正文。"""

        def get_batch(self, npc_id, node_ids):
            return [{"node_id": node_id, "type": "event", "value": "深层千早线索" if node_id == "n5" else "中间线索", "importance": 0.8} for node_id in node_ids]

    graph, nodes = ChainGraph(), ChainNodes()
    local = DirectedDeepRetriever(graph, nodes).search(DeepSearchRequest(
        npc_id="kujo", target_id="player", start_node_ids=["n0"], target_start_id=None,
        direction=RetrievalDirection(entity_mentions=["千早"]),
        policy=LocalSearchPolicy(SearchBudget(7, 1, 1, 20, 0, 10, 0.0, 0.0)),
    ))
    assert local.node_ids[-1] == "n5"
    full_llm = LlmGraphRetriever(graph, nodes).search(LlmGraphSearchRequest(
        npc_id="kujo", target_id="player", start_node_ids=["n0"], route_context={"_direction": RetrievalDirection(entity_mentions=["千早"])},
        policy=LlmRoutePolicy(7, 1, 1, 1, 1, 7, 64, 512),
    ))
    assert full_llm.node_ids[-1] == "n5"
