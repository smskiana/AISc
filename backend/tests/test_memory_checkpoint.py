"""Python 记忆检查点测试。"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.src.save.memory_checkpoint import MEMORY_TABLES, MemoryCheckpointService


class MemoryCheckpointTests(unittest.TestCase):
    """验证记忆检查点的状态边界和原子提交。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.database = root / "game.db"
        self.lancedb = root / "lancedb"
        self.checkpoints = root / "checkpoints"
        self.lancedb.mkdir()
        (self.lancedb / "vectors.bin").write_bytes(b"memory-vector")
        connection = sqlite3.connect(self.database)
        for table in MEMORY_TABLES:
            connection.execute(f'CREATE TABLE "{table}" (value TEXT)')
            connection.execute(f'INSERT INTO "{table}" VALUES (?)', (f"{table}_old",))
        connection.execute("CREATE TABLE npc_states (value TEXT)")
        connection.execute("INSERT INTO npc_states VALUES ('world_old')")
        connection.execute("CREATE TABLE player_inventory (value TEXT)")
        connection.execute("CREATE TABLE game_state (value TEXT)")
        connection.commit()
        connection.close()
        self.service = MemoryCheckpointService(
            str(self.database), str(self.lancedb), str(self.checkpoints)
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_checkpoint_excludes_world_tables_and_restores_memory_only(self) -> None:
        """加载检查点不得覆盖 Unity 权威世界表。"""
        self.service.prepare("1", "checkpoint_1")
        self.service.commit("1", "checkpoint_1")
        checkpoint_db = self.checkpoints / "slot_1" / "memory.db"
        saved = sqlite3.connect(checkpoint_db)
        self.assertIsNone(saved.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='npc_states'"
        ).fetchone())
        saved.close()

        live = sqlite3.connect(self.database)
        live.execute("UPDATE memory_nodes SET value='memory_new'")
        live.execute("UPDATE npc_states SET value='world_new'")
        live.commit()
        live.close()

        self.service.load("1", "checkpoint_1")
        live = sqlite3.connect(self.database)
        self.assertEqual(live.execute("SELECT value FROM memory_nodes").fetchone()[0], "memory_nodes_old")
        self.assertEqual(live.execute("SELECT value FROM npc_states").fetchone()[0], "world_new")
        live.close()

    def test_abort_preserves_existing_checkpoint(self) -> None:
        """中止新检查点不得删除已经提交的正式检查点。"""
        self.service.prepare("1", "checkpoint_1")
        self.service.commit("1", "checkpoint_1")
        self.service.prepare("1", "checkpoint_2")
        self.service.abort("1", "checkpoint_2")
        manifest = self.service.list_checkpoints()[0]
        self.assertEqual(manifest["checkpoint_id"], "checkpoint_1")

    def test_abort_after_commit_restores_previous_checkpoint(self) -> None:
        """双端最终确认前中止应恢复上一正式记忆检查点。"""
        self.service.prepare("1", "checkpoint_1")
        self.service.commit("1", "checkpoint_1")
        self.service.finalize("1", "checkpoint_1")
        self.service.prepare("1", "checkpoint_2")
        self.service.commit("1", "checkpoint_2")
        self.service.abort("1", "checkpoint_2")
        manifest = self.service.list_checkpoints()[0]
        self.assertEqual(manifest["checkpoint_id"], "checkpoint_1")

    def test_delete_removes_matching_checkpoint(self) -> None:
        """删除应校验 checkpoint 身份并移除正式槽位。"""
        self.service.prepare("1", "checkpoint_1")
        self.service.commit("1", "checkpoint_1")
        self.service.finalize("1", "checkpoint_1")

        self.service.delete("1", "checkpoint_1")

        self.assertFalse((self.checkpoints / "slot_1").exists())

    def test_purge_all_removes_final_backup_and_pending_checkpoints(self) -> None:
        """新游戏清理应永久移除全部检查点形态，并保留可继续保存的空根目录。"""
        self.service.prepare("1", "checkpoint_1")
        self.service.commit("1", "checkpoint_1")
        self.service.prepare("1", "checkpoint_2")
        self.service.commit("1", "checkpoint_2")
        self.service.prepare("2", "checkpoint_3")

        self.service.purge_all()

        self.assertEqual(self.service.list_checkpoints(), [])
        self.assertTrue(self.checkpoints.is_dir())
        self.assertTrue((self.checkpoints / ".pending").is_dir())
        self.assertEqual(list(self.checkpoints.iterdir()), [self.checkpoints / ".pending"])

    def test_corrupted_file_is_rejected(self) -> None:
        """摘要不一致的检查点必须拒绝加载。"""
        self.service.prepare("1", "checkpoint_1")
        self.service.commit("1", "checkpoint_1")
        (self.checkpoints / "slot_1" / "memory.db").write_bytes(b"broken")
        with self.assertRaisesRegex(ValueError, "checkpoint_corrupted"):
            self.service.load("1", "checkpoint_1")


if __name__ == "__main__":
    unittest.main()
