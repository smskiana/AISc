"""
存档管理器 — SQLite 热备份 + manifest 验证。
"""
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime

from ..database.sqlite_client import SQLiteClient

logger = logging.getLogger("sakurabashi.save")


# 仅供旧 SAVE_REQUEST / LOAD_REQUEST 兼容；新流程使用 MemoryCheckpointService。
class SaveManager:
    """存档管理"""

    def __init__(self, db: SQLiteClient, save_dir: str, data_dir: str):
        self.db = db
        self.save_dir = Path(save_dir)
        self.data_dir = Path(data_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

    # ════════════════════════════════
    # 保存
    # ════════════════════════════════

    def save(self, slot: str, game_time: dict, weather: str,
             player_location: str, npcs: list[dict]) -> dict:
        """
        保存当前游戏状态到指定存档槽。
        返回 {"success": true, "slot": "1", "manifest": {...}}
        """
        slot_dir = self.save_dir / f"slot_{slot}"
        slot_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. SQLite 热备份
            import sqlite3
            src = sqlite3.connect(str(self.data_dir / "game.db"))
            dst = sqlite3.connect(str(slot_dir / "game.db"))
            src.backup(dst)
            dst.close()
            src.close()

            # 1.1 LanceDB 目录备份（如果存在）
            lancedb_src = self.data_dir / "lancedb"
            lancedb_dst = slot_dir / "lancedb"
            if lancedb_dst.exists():
                shutil.rmtree(lancedb_dst, ignore_errors=True)
            if lancedb_src.exists():
                shutil.copytree(lancedb_src, lancedb_dst)

            # 2. 游戏状态快照 (JSON)
            snapshot = {
                "game_time": game_time,
                "weather": weather,
                "player_location": player_location,
                "npcs": npcs,
                "saved_at": datetime.now().isoformat(),
                "version": "0.2.0",
            }
            with open(slot_dir / "snapshot.json", "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)

            # 3. Manifest
            db_size = (slot_dir / "game.db").stat().st_size
            manifest = {
                "slot": slot,
                "version": "0.2.0",
                "saved_at": snapshot["saved_at"],
                "game_day": game_time.get("day", 1),
                "db_size_bytes": db_size,
                "files": ["game.db", "snapshot.json"] + (["lancedb"] if lancedb_src.exists() else []),
            }
            with open(slot_dir / "manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            logger.info(f"存档成功: slot_{slot} (Day {game_time.get('day',1)}, {db_size//1024}KB)")
            return {"success": True, "slot": slot, "manifest": manifest}

        except Exception as e:
            logger.error(f"存档失败 slot_{slot}: {e}")
            # 清理失败存档
            if slot_dir.exists():
                shutil.rmtree(slot_dir, ignore_errors=True)
            return {"success": False, "error": str(e)}

    # ════════════════════════════════
    # 加载
    # ════════════════════════════════

    def load(self, slot: str) -> dict | None:
        """
        加载存档。返回快照数据，或 None（存档损坏/不存在）。
        """
        slot_dir = self.save_dir / f"slot_{slot}"

        # 验证
        manifest_path = slot_dir / "manifest.json"
        db_path = slot_dir / "game.db"
        if not manifest_path.exists() or not db_path.exists():
            logger.warning(f"存档 slot_{slot} 不存在或不完整")
            return None

        # 验证 manifest
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            if db_path.stat().st_size != manifest.get("db_size_bytes", -1):
                logger.warning(f"存档 slot_{slot} 大小不匹配，可能损坏")
        except Exception:
            pass

        # 恢复 SQLite
        try:
            import sqlite3
            src = sqlite3.connect(str(db_path))
            dst = sqlite3.connect(str(self.data_dir / "game.db"))
            src.backup(dst)
            dst.close()
            src.close()
        except Exception as e:
            logger.error(f"数据库恢复失败 slot_{slot}: {e}")
            return None

        if not self._migrate_restored_database(slot):
            return None

        # 恢复 LanceDB 目录（如有）
        lancedb_src = slot_dir / "lancedb"
        lancedb_dst = self.data_dir / "lancedb"
        if lancedb_src.exists():
            try:
                if lancedb_dst.exists():
                    shutil.rmtree(lancedb_dst, ignore_errors=True)
                shutil.copytree(lancedb_src, lancedb_dst)
            except Exception as e:
                logger.warning(f"LanceDB 恢复失败 slot_{slot}: {e}")

        # 读取快照
        snapshot_path = slot_dir / "snapshot.json"
        if snapshot_path.exists():
            with open(snapshot_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return {"game_time": {"day": 1, "hour": 8, "minute": 0}}

    def _migrate_restored_database(self, slot: str) -> bool:
        """读档覆盖运行库后立即执行 SQLite 迁移，兼容旧版存档。"""
        try:
            SQLiteClient(str(self.data_dir / "game.db"))
            return True
        except Exception as e:
            logger.error(f"数据库迁移失败 slot_{slot}: {e}")
            return False

    # ════════════════════════════════
    # 列表
    # ════════════════════════════════

    def list_saves(self) -> list[dict]:
        """列出所有存档"""
        saves = []
        for slot_dir in sorted(self.save_dir.iterdir()):
            if not slot_dir.is_dir() or not slot_dir.name.startswith("slot_"):
                continue
            manifest_path = slot_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        m = json.load(f)
                    saves.append({
                        "slot": m.get("slot", slot_dir.name.replace("slot_", "")),
                        "game_day": m.get("game_day", "?"),
                        "saved_at": m.get("saved_at", ""),
                        "version": m.get("version", ""),
                    })
                except Exception:
                    pass
        return sorted(saves, key=lambda s: s["slot"])
