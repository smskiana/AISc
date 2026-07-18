"""冷启动初始知识投影的 SQLite、向量写入和幂等集成测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.src.database.sqlite_client import SQLiteClient
from backend.src.memory.initial_knowledge_diagnostics import build_initial_knowledge_snapshot
from backend.src.npc.state_manager import StateManager


class _Vector:
    """提供 LanceDB 初始化所需的最小可序列化向量。"""

    def tolist(self) -> list[float]:
        """返回固定维度的零向量。"""
        return [0.0]


class _FakeVectorStore:
    """记录冷启动批量向量写入，不依赖本地 embedding 模型。"""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, dict]] = {}

    def clear_all(self) -> None:
        """清空模拟 LanceDB 表。"""
        self.rows.clear()

    def upsert_nodes(self, npc_id: str, nodes: list[dict]) -> None:
        """按 NPC 保存批量写入节点。"""
        table = self.rows.setdefault(npc_id, {})
        for node in nodes:
            table[node["node_id"]] = dict(node)

    def get_batch(self, npc_id: str, node_ids: list[str]) -> list[dict]:
        """返回模拟 LanceDB 的节点数据。"""
        table = self.rows.get(npc_id, {})
        return [table[node_id] for node_id in node_ids if node_id in table]


class InitialKnowledgeColdStartTests(unittest.TestCase):
    """验证投影实际落入独立 NPC 图并可重复生成。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = SQLiteClient(str(Path(self.temp_dir.name) / "game.db"))
        self.vector_store = _FakeVectorStore()
        self.manager = StateManager(self.db, self.vector_store)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cold_start_writes_projection_sources_nodes_edges_and_vectors(self) -> None:
        """公开身份事实应带人物边，秘密只出现在主体自己的图中。"""
        with patch(
            "backend.src.memory.embedding.encode_batch",
            side_effect=lambda values: [_Vector() for _ in values],
        ):
            self.manager.cold_start()

        sakura_rows = self.db.get_initial_projections("sakura")
        bakery = next(row for row in sakura_rows if row["source_fact_id"] == "chihaya_bakery_identity")
        self.assertEqual(bakery["projection_id"], "initial_knowledge__sakura__chihaya_bakery_identity")
        self.assertIn(bakery["node_id"], self.vector_store.rows["sakura"])

        edges = self.db.get_initial_projection_edges([bakery["node_id"]])
        edge_targets = {edge["node_b"] for edge in edges} | {edge["node_a"] for edge in edges}
        chihaya_nodes = {
            row["id"]
            for row in self.db.fetchall(
                "SELECT id FROM memory_nodes WHERE subject_id = 'sakura'"
            )
        }
        self.assertTrue(edge_targets & chihaya_nodes)
        self.assertTrue(any(edge["id"].endswith("_chihaya") for edge in edges))

        sakura_secret = self.db.get_initial_projections("sakura", "sakura_hidden_heart_condition")
        self.assertEqual(len(sakura_secret), 1)
        self.assertEqual(
            self.db.get_initial_projections("chihaya", "sakura_hidden_heart_condition"),
            [],
        )

    def test_repeated_cold_start_keeps_one_stable_projection_and_edges(self) -> None:
        """重复新开局应重建同一组稳定投影，不累积来源或边。"""
        with patch(
            "backend.src.memory.embedding.encode_batch",
            side_effect=lambda values: [_Vector() for _ in values],
        ):
            self.manager.cold_start()
            first_projection = self.db.get_initial_projections("sakura", "chihaya_bakery_identity")[0]
            first_edges = self.db.get_initial_projection_edges([first_projection["node_id"]])
            self.manager.cold_start()

        second_projection = self.db.get_initial_projections("sakura", "chihaya_bakery_identity")
        second_edges = self.db.get_initial_projection_edges([first_projection["node_id"]])
        self.assertEqual(len(second_projection), 1)
        self.assertEqual(second_projection[0]["projection_id"], first_projection["projection_id"])
        self.assertEqual(second_projection[0]["node_id"], first_projection["node_id"])
        self.assertEqual(
            [edge["id"] for edge in second_edges],
            [edge["id"] for edge in first_edges],
        )

    def test_diagnostic_snapshot_explains_inclusion_and_exclusion(self) -> None:
        """诊断应返回实际边，且排除项不得携带运行时节点标识。"""
        with patch(
            "backend.src.memory.embedding.encode_batch",
            side_effect=lambda values: [_Vector() for _ in values],
        ):
            self.manager.cold_start()

        snapshot = build_initial_knowledge_snapshot(
            self.db,
            self.vector_store,
            Path(__file__).parents[1] / "config" / "initial_knowledge.json",
            "chihaya",
            include_excluded=True,
        )
        included = next(item for item in snapshot["items"] if item["fact_id"] == "chihaya_bakery_identity")
        excluded = next(item for item in snapshot["items"] if item["fact_id"] == "sakura_hidden_heart_condition")
        self.assertEqual(included["status"], "included")
        self.assertTrue(included["edge_ids"])
        self.assertEqual(excluded["status"], "excluded")
        self.assertEqual(excluded["node_id"], "")
        self.assertEqual(excluded["edge_ids"], [])


if __name__ == "__main__":
    unittest.main()
