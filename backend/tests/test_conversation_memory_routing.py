"""逐轮对话工作记忆、实体解析和结构化检索回归测试。"""
from __future__ import annotations

import unittest

from backend.src.dialogue.conversation_context import ConversationTurn, ConversationTurnRequest
from backend.src.dialogue.conversation_memory import ConversationMemoryCoordinator, ConversationWorkingMemory
from backend.src.memory.retrieval import (
    RETRIEVAL_MODE_CONFIGS,
    RetrievalEngine,
    RetrievalRequest,
    RetrievalResult,
)


class FakeDatabase:
    """提供关系读取和空短期记忆所需的最小数据库替身。"""

    def __init__(self):
        """记录实际查询过的关系目标。"""
        self.relationship_targets: list[str] = []

    def fetchone(self, query, params=()):
        """按 owner-target 返回可区分的关系记录。"""
        if "npc_impressions" in query:
            target_id = params[1]
            self.relationship_targets.append(target_id)
            return {
                "baseline_impression": f"impression:{target_id}",
                "delta_note": "",
            }
        if "npc_bonds" in query:
            target_id = params[1]
            return {"bond": 0.8 if target_id == "player" else 0.45}
        if "npc_states" in query:
            return {"emotion": "平静", "energy": 80, "current_need": None}
        return None

    def fetchall(self, query, params=()):
        """默认不提供持久化短期记忆。"""
        return []


class CapturingRetrieval:
    """捕获协调器传入的结构化请求。"""

    def __init__(self):
        self.requests: list[RetrievalRequest] = []

    def retrieve(self, request):
        """返回稳定的结构化诊断结果。"""
        self.requests.append(request)
        return RetrievalResult(
            rebuilt_context="九条记得千早。",
            start_node_ids=["kujo:self", "kujo:person:player"],
            selected_edge_ids=["edge_kujo_chihaya"],
            retrieved_node_ids=["memory_chihaya"],
            vector_query_preview=request.query_text,
        )


class FakeGraphDatabase(FakeDatabase):
    """提供 self、玩家和千早人物节点的最小图结构。"""

    def get_nodes_by_npc(self, npc_id):
        """返回图节点 ID。"""
        return [{"id": "self"}, {"id": "player"}, {"id": "chihaya"}]

    def get_directional_neighbors(self, node_id, limit=10):
        """只允许从 self 沿真实边命中千早节点。"""
        if node_id == "self":
            return [{
                "id": "edge_kujo_chihaya",
                "neighbor_id": "chihaya",
                "directional_clarity": 0.9,
                "type": "relationship",
                "direction": "ab",
                "target_importance": 0.8,
            }]
        return []


class FakeVectorStore:
    """返回稳定人物节点并避免真实 embedding 依赖。"""

    def get_batch(self, npc_id, node_ids):
        """按请求 ID 返回人物节点内容。"""
        nodes = {
            "self": {"node_id": "self", "type": "self", "value": "我", "importance": 1.0},
            "player": {"node_id": "player", "type": "person", "value": "小李", "importance": 0.5},
            "chihaya": {"node_id": "chihaya", "type": "person", "value": "千早", "importance": 0.5},
        }
        return [nodes[node_id] for node_id in node_ids if node_id in nodes]

    def search(self, npc_id, vector, top_k=5):
        """本测试不需要向量兜底结果。"""
        return []


class FakeCompetitionGraphDatabase(FakeDatabase):
    """提供明确人物与玩家背景互相竞争的图结构。"""

    def get_nodes_by_npc(self, npc_id):
        """返回 self、玩家、千早和若干背景事件节点。"""
        return [
            {"id": "self"},
            {"id": "player"},
            {"id": "chihaya"},
            {"id": "event_city"},
            {"id": "event_cafe"},
            {"id": "event_street"},
        ]

    def get_directional_neighbors(self, node_id, limit=10):
        """从固定起点暴露人物关系和高 clarity 背景事件。"""
        if node_id == "self":
            return [
                {
                    "id": "edge_kujo_chihaya",
                    "neighbor_id": "chihaya",
                    "directional_clarity": 0.74,
                    "type": "relationship",
                    "direction": "ab",
                    "target_importance": 0.9,
                },
                {
                    "id": "edge_city_background",
                    "neighbor_id": "event_city",
                    "directional_clarity": 0.97,
                    "type": "involved",
                    "direction": "ba",
                    "target_importance": 0.9,
                },
                {
                    "id": "edge_street_background",
                    "neighbor_id": "event_street",
                    "directional_clarity": 0.93,
                    "type": "involved",
                    "direction": "ba",
                    "target_importance": 0.84,
                },
            ]
        if node_id == "player":
            return [{
                "id": "edge_player_cafe",
                "neighbor_id": "event_cafe",
                "directional_clarity": 0.96,
                "type": "involved",
                "direction": "ba",
                "target_importance": 0.92,
            }]
        return []


class FakeCompetitionVectorStore(FakeVectorStore):
    """返回竞争图测试需要的节点元数据。"""

    def get_batch(self, npc_id, node_ids):
        """按请求 ID 返回人物和背景事件节点。"""
        nodes = {
            "self": {"node_id": "self", "type": "self", "value": "我", "importance": 1.0},
            "player": {"node_id": "player", "type": "person", "value": "小李", "importance": 0.5},
            "chihaya": {"node_id": "chihaya", "type": "person", "value": "千早", "importance": 0.9},
            "event_city": {
                "node_id": "event_city",
                "type": "event",
                "value": "Day 0 前，大家知道小李小时候在樱桥通长大，后来从城市回来。",
                "importance": 0.9,
                "created_day": 0,
            },
            "event_cafe": {
                "node_id": "event_cafe",
                "type": "event",
                "value": "Day 0 前后，街上听说小李准备重新开奶奶留下的喫茶店。",
                "importance": 0.92,
                "created_day": 0,
            },
            "event_street": {
                "node_id": "event_street",
                "type": "event",
                "value": "樱桥通不大，商店街几家店彼此都认识。",
                "importance": 0.84,
                "created_day": 0,
            },
        }
        return [nodes[node_id] for node_id in node_ids if node_id in nodes]


class ConversationMemoryRoutingTests(unittest.TestCase):
    """验证方案要求的逐轮文本刷新和固定起点边界。"""

    def test_current_utterance_refreshes_retrieval_without_topic_relationship_lookup(self) -> None:
        """询问千早时只读取玩家参与者关系，并把原文交给检索器。"""
        retrieval = CapturingRetrieval()
        database = FakeDatabase()
        coordinator = ConversationMemoryCoordinator(database, retrieval)
        context = coordinator.prepare_turn_context(ConversationTurnRequest(
            conversation_id="dialogue_1",
            speaker_id="kujo",
            listener_ids=["player"],
            utterance="千早是谁？",
            location_id="bookstore.counter",
            game_time="第1天 10:00",
            mode="player_dialogue",
        ))

        self.assertEqual([item.target_id for item in context.participant_impressions], ["player"])
        self.assertEqual(database.relationship_targets, ["player"])
        self.assertEqual(retrieval.requests[0].query_text, "千早是谁？")

    def test_recent_dialogue_is_forwarded_without_entity_state(self) -> None:
        """近期对白原文进入结构化检索请求，不派生话题实体状态。"""
        retrieval = CapturingRetrieval()
        coordinator = ConversationMemoryCoordinator(FakeDatabase(), retrieval)
        coordinator.prepare_turn_context(ConversationTurnRequest(
            conversation_id="dialogue_history",
            speaker_id="kujo",
            listener_ids=["player"],
            utterance="千早是谁？",
            location_id="street.crossroad",
            game_time="第1天 10:00",
            mode="player_dialogue",
            history=[ConversationTurn("player", "（玩家走到了你面前。）")],
        ))

        self.assertEqual(retrieval.requests[0].recent_turns[0].text, "（玩家走到了你面前。）")

    def test_working_memory_rolls_old_turns_without_losing_recent_window(self) -> None:
        """超长会话压缩旧轮次并保留最近八轮完整文本。"""
        memory = ConversationWorkingMemory("dialogue_2", ["kujo", "player"])
        for index in range(12):
            memory.append_turn(ConversationTurn("player" if index % 2 == 0 else "kujo", f"第{index}轮"))

        self.assertEqual(len(memory.turns), 8)
        self.assertEqual(memory.turns[0].text, "第4轮")
        self.assertIn("第0轮", memory.rolling_summary)
        self.assertIn("第3轮", memory.rolling_summary)

    def test_structured_retrieval_keeps_fixed_starts_and_discovers_chihaya_by_edge(self) -> None:
        """千早不是起点，但可从固定起点沿实际图边命中。"""
        engine = RetrievalEngine(FakeGraphDatabase(), FakeVectorStore())
        result = engine.retrieve(RetrievalRequest(
            npc_id="kujo",
            conversation_participant_ids=["player"],
            query_text="千早是谁？",
            recent_turns=[ConversationTurn("player", "你认识千早吗？")],
            location_id="bookstore.counter",
            game_time="第1天 10:00",
            mode="player_dialogue",
        ))

        self.assertEqual(result.start_node_ids, ["self", "player"])
        self.assertEqual(result.selected_edge_ids, ["edge_kujo_chihaya"])
        self.assertEqual(result.retrieved_node_ids, ["chihaya"])
        self.assertIn("千早是谁？", result.vector_query_preview)
        self.assertIn("你认识千早吗？", result.vector_query_preview)

    def test_named_person_question_beats_high_clarity_player_background_edges(self) -> None:
        """明确点名千早时，本地图候选排序应选中千早关系边。"""
        original = dict(RETRIEVAL_MODE_CONFIGS["player_dialogue"])
        RETRIEVAL_MODE_CONFIGS["player_dialogue"].update({
            "edges_per_route": 2,
            "max_hops": 1,
            "min_graph_nodes": 1,
            "vector_fallback_limit": 0,
            "local_route_min_score": 0.0,
            "local_route_margin": -999.0,
            "final_memory_limit": 5,
        })
        try:
            engine = RetrievalEngine(FakeCompetitionGraphDatabase(), FakeCompetitionVectorStore())
            result = engine.retrieve(RetrievalRequest(
                npc_id="kujo",
                conversation_participant_ids=["player"],
                query_text="你知道千早在哪吗",
                recent_turns=[
                    ConversationTurn("player", "（玩家走到了你面前。）"),
                    ConversationTurn("kujo", "喫茶店那边的小李？有事？"),
                    ConversationTurn("player", "你知道千早在哪吗"),
                ],
                location_id="bookstore.counter",
                game_time="第1天 10:00",
                mode="player_dialogue",
            ))
        finally:
            RETRIEVAL_MODE_CONFIGS["player_dialogue"].clear()
            RETRIEVAL_MODE_CONFIGS["player_dialogue"].update(original)

        self.assertEqual(result.start_node_ids, ["self", "player"])
        self.assertIn("edge_kujo_chihaya", result.selected_edge_ids)
        self.assertIn("chihaya", result.retrieved_node_ids)
        self.assertFalse(result.fallback_used)

    def test_player_cafe_question_still_prefers_player_background(self) -> None:
        """没有明确人物命中时，玩家喫茶店背景仍能优先进入图路径。"""
        original = dict(RETRIEVAL_MODE_CONFIGS["player_dialogue"])
        RETRIEVAL_MODE_CONFIGS["player_dialogue"].update({
            "edges_per_route": 2,
            "max_hops": 1,
            "min_graph_nodes": 1,
            "vector_fallback_limit": 0,
            "local_route_min_score": 0.0,
            "local_route_margin": -999.0,
            "final_memory_limit": 5,
        })
        try:
            engine = RetrievalEngine(FakeCompetitionGraphDatabase(), FakeCompetitionVectorStore())
            result = engine.retrieve(RetrievalRequest(
                npc_id="kujo",
                conversation_participant_ids=["player"],
                query_text="喫茶店最近怎么样？",
                recent_turns=[ConversationTurn("player", "喫茶店最近怎么样？")],
                location_id="player_cafe.counter",
                game_time="第1天 10:00",
                mode="player_dialogue",
            ))
        finally:
            RETRIEVAL_MODE_CONFIGS["player_dialogue"].clear()
            RETRIEVAL_MODE_CONFIGS["player_dialogue"].update(original)

        self.assertEqual(result.selected_edge_ids[0], "edge_player_cafe")
        self.assertIn("event_cafe", result.retrieved_node_ids)
        self.assertFalse(result.fallback_used)

    def test_query_entity_top_candidate_uses_local_route_despite_background_tie(self) -> None:
        """当前发言强命中的 top1 明确领先时，不因背景边接近而交给 LLM。"""
        engine = RetrievalEngine(FakeCompetitionGraphDatabase(), FakeCompetitionVectorStore())
        config = RETRIEVAL_MODE_CONFIGS["player_dialogue"]
        request = RetrievalRequest(
            npc_id="kujo",
            conversation_participant_ids=["player"],
            query_text="你知道千早在哪吗",
            recent_turns=[
                ConversationTurn("player", "（玩家走到了你面前。）"),
                ConversationTurn("kujo", "喫茶店那边的小李？有事？"),
                ConversationTurn("player", "你知道千早在哪吗"),
            ],
            location_id="police_box.desk",
            game_time="第1天 10:00",
            mode="player_dialogue",
        )
        start_ids, target_start_id = engine._find_start_nodes("kujo", "player")
        route_context = engine._build_route_context(
            npc_id="kujo",
            target_id="player",
            location=request.location_id,
            game_time=request.game_time,
            config=config,
            mode="player_dialogue",
            request=request,
        )
        route_context["_diagnostics"] = {"llm_route_calls": 0, "local_route_skips": 0}
        candidates = engine._collect_candidate_edges(
            npc_id="kujo",
            target_id="player",
            frontier=start_ids,
            target_start_id=target_start_id,
            route_context=route_context,
            visited_nodes=set(start_ids),
            visited_edges=set(),
            max_edges_per_hop=int(config["max_edges_per_hop"]),
        )

        self.assertEqual(candidates[0]["edge_id"], "edge_kujo_chihaya")
        self.assertTrue(engine._can_use_local_route(route_context, candidates, int(config["edges_per_route"])))


if __name__ == "__main__":
    unittest.main()
