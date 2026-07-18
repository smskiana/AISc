"""AI 记忆检查点的原子保存、验证和恢复。"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MEMORY_TABLES = (
    "npc_bonds",
    "memory_nodes",
    "memory_edges",
    "short_term_memories",
    "player_memories",
    "npc_impressions",
    "memory_merge_sources",
    "memory_retrieval_logs",
    "memory_initial_projections",
)
WORLD_TABLES = ("npc_states", "player_inventory", "game_state")


class MemoryCheckpointService:
    """管理与 Unity checkpoint_id 关联的 Python 记忆检查点。"""

    def __init__(self, database_path: str, lancedb_path: str, checkpoint_root: str):
        """绑定运行数据路径并建立检查点临时目录。"""
        self.database_path = Path(database_path)
        self.lancedb_path = Path(lancedb_path)
        self.checkpoint_root = Path(checkpoint_root)
        self.pending_root = self.checkpoint_root / ".pending"
        self.checkpoint_root.mkdir(parents=True, exist_ok=True)
        self.pending_root.mkdir(parents=True, exist_ok=True)

    def prepare(self, slot_id: str, checkpoint_id: str) -> dict:
        """在临时目录生成经过摘要校验的记忆检查点。"""
        self._validate_id(slot_id, "slot_id")
        self._validate_id(checkpoint_id, "checkpoint_id")
        pending = self._pending_path(slot_id, checkpoint_id)
        if pending.exists():
            shutil.rmtree(pending)
        pending.mkdir(parents=True)

        memory_db = pending / "memory.db"
        self._backup_memory_database(memory_db)
        if self.lancedb_path.exists():
            shutil.copytree(self.lancedb_path, pending / "lancedb")

        files = self._build_file_hashes(pending)
        manifest = {
            "slot_id": slot_id,
            "checkpoint_id": checkpoint_id,
            "memory_schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "memory_tables": list(MEMORY_TABLES),
            "files": files,
        }
        self._write_json(pending / "manifest.json", manifest)
        return manifest

    def commit(self, slot_id: str, checkpoint_id: str) -> dict:
        """验证临时检查点并原子替换槽位中的正式记忆检查点。"""
        pending = self._pending_path(slot_id, checkpoint_id)
        manifest = self._validate_checkpoint(pending, slot_id, checkpoint_id)
        final_path = self._final_path(slot_id)
        backup_path = final_path.with_name(f"{final_path.name}.previous")
        if backup_path.exists():
            shutil.rmtree(backup_path)
        if final_path.exists():
            final_path.replace(backup_path)
        try:
            pending.replace(final_path)
        except Exception:
            if backup_path.exists() and not final_path.exists():
                backup_path.replace(final_path)
            raise
        return manifest

    def abort(self, slot_id: str, checkpoint_id: str) -> None:
        """清理临时检查点；若新检查点已提交则恢复上一正式版本。"""
        pending = self._pending_path(slot_id, checkpoint_id)
        if pending.exists():
            shutil.rmtree(pending)
        final_path = self._final_path(slot_id)
        backup_path = final_path.with_name(f"{final_path.name}.previous")
        if final_path.exists():
            try:
                manifest = json.loads((final_path / "manifest.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manifest = {}
            if manifest.get("checkpoint_id") == checkpoint_id:
                shutil.rmtree(final_path)
                if backup_path.exists():
                    backup_path.replace(final_path)

    def finalize(self, slot_id: str, checkpoint_id: str) -> dict:
        """确认双方提交成功后删除上一记忆检查点备份。"""
        final_path = self._final_path(slot_id)
        manifest = self._validate_checkpoint(final_path, slot_id, checkpoint_id)
        backup_path = final_path.with_name(f"{final_path.name}.previous")
        if backup_path.exists():
            shutil.rmtree(backup_path)
        return manifest

    def load(self, slot_id: str, checkpoint_id: str) -> dict:
        """验证正式检查点并只恢复记忆表与向量目录。"""
        source = self._final_path(slot_id)
        manifest = self._validate_checkpoint(source, slot_id, checkpoint_id)
        self._restore_memory_tables(source / "memory.db")
        source_lancedb = source / "lancedb"
        if source_lancedb.exists():
            replacement = self.lancedb_path.with_name(f"{self.lancedb_path.name}.loading")
            if replacement.exists():
                shutil.rmtree(replacement)
            shutil.copytree(source_lancedb, replacement)
            if self.lancedb_path.exists():
                shutil.rmtree(self.lancedb_path)
            replacement.replace(self.lancedb_path)
        return manifest

    def list_checkpoints(self) -> list[dict]:
        """列出可通过 manifest 验证的正式记忆检查点。"""
        result = []
        for path in sorted(self.checkpoint_root.glob("slot_*")):
            manifest_path = path / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                result.append(json.loads(manifest_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return result

    def delete(self, slot_id: str, checkpoint_id: str) -> None:
        """校验身份后删除指定正式记忆检查点。"""
        final_path = self._final_path(slot_id)
        self._validate_checkpoint(final_path, slot_id, checkpoint_id)
        shutil.rmtree(final_path)
        backup_path = final_path.with_name(f"{final_path.name}.previous")
        if backup_path.exists():
            shutil.rmtree(backup_path)

    def purge_all(self) -> None:
        """永久删除全部正式、备份和待提交记忆检查点，并重建空临时目录。"""
        if self.checkpoint_root.exists():
            shutil.rmtree(self.checkpoint_root)
        self.checkpoint_root.mkdir(parents=True, exist_ok=True)
        self.pending_root.mkdir(parents=True, exist_ok=True)

    def _backup_memory_database(self, destination: Path) -> None:
        """热备份运行数据库，并从副本中删除 Unity 权威世界表。"""
        source_connection = sqlite3.connect(str(self.database_path))
        destination_connection = sqlite3.connect(str(destination))
        try:
            source_connection.backup(destination_connection)
            for table in WORLD_TABLES:
                destination_connection.execute(f'DROP TABLE IF EXISTS "{table}"')
            destination_connection.commit()
        finally:
            destination_connection.close()
            source_connection.close()

    def _restore_memory_tables(self, source_database: Path) -> None:
        """在单个 SQLite 事务中只替换记忆表。"""
        connection = sqlite3.connect(str(self.database_path))
        try:
            connection.execute("ATTACH DATABASE ? AS checkpoint", (str(source_database),))
            connection.execute("BEGIN IMMEDIATE")
            for table in MEMORY_TABLES:
                exists = connection.execute(
                    "SELECT 1 FROM checkpoint.sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if not exists:
                    raise ValueError(f"记忆检查点缺少表: {table}")
                connection.execute(f'DELETE FROM main."{table}"')
                connection.execute(f'INSERT INTO main."{table}" SELECT * FROM checkpoint."{table}"')
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _validate_checkpoint(self, path: Path, slot_id: str, checkpoint_id: str) -> dict:
        """校验检查点身份和所有文件 SHA-256。"""
        manifest_path = path / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"记忆检查点不存在: {checkpoint_id}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("slot_id") != slot_id or manifest.get("checkpoint_id") != checkpoint_id:
            raise ValueError("checkpoint_mismatch")
        for relative_path, expected_hash in manifest.get("files", {}).items():
            file_path = path / relative_path
            if not file_path.is_file() or self._sha256(file_path) != expected_hash:
                raise ValueError(f"checkpoint_corrupted:{relative_path}")
        return manifest

    def _build_file_hashes(self, root: Path) -> dict[str, str]:
        """为检查点内除 manifest 外的文件生成稳定摘要。"""
        return {
            path.relative_to(root).as_posix(): self._sha256(path)
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.name != "manifest.json"
        }

    @staticmethod
    def _sha256(path: Path) -> str:
        """流式计算文件 SHA-256。"""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        """以 UTF-8 写入稳定格式 JSON。"""
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        """拒绝可能逃逸检查点目录的非法跨端 ID。"""
        if not value or not all(character.islower() or character.isdigit() or character == "_" for character in value):
            raise ValueError(f"invalid_{field_name}")

    def _pending_path(self, slot_id: str, checkpoint_id: str) -> Path:
        """返回一次保存尝试的临时检查点目录。"""
        return self.pending_root / f"slot_{slot_id}_{checkpoint_id}"

    def _final_path(self, slot_id: str) -> Path:
        """返回指定槽位的正式记忆检查点目录。"""
        return self.checkpoint_root / f"slot_{slot_id}"
