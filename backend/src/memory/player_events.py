"""玩家真实事件写入器：把玩家行动转成 NPC 可见的短期记忆。"""
from __future__ import annotations

import json
import logging
import uuid

from ..database.sqlite_client import SQLiteClient
from ..world.proximity import are_nearby

logger = logging.getLogger("sakurabashi.player_events")

NPC_IDS = ["sakura", "chihaya", "kazuha", "tatsunosuke", "kujo"]


class PlayerEventMemoryWriter:
    """将玩家关键行动写入见证 NPC 的短期记忆，后续由午夜流程入图。"""

    def __init__(self, db: SQLiteClient):
        self.db = db

    def record_event(self, msg: dict, game_time: str) -> dict:
        """记录玩家事件并返回写入结果。"""
        content = str(msg.get("content", "")).strip()
        if not content:
            return {"success": False, "error": "empty_content", "written": []}

        location_id = str(msg.get("location_id") or msg.get("location") or "player_cafe.doorway")
        event_type = str(msg.get("event_type") or "player_action")
        importance = self._clamp_importance(msg.get("importance", 0.7))
        witnesses = self._resolve_witnesses(msg.get("witness_npcs"), location_id)
        rumor_mode = not bool(msg.get("witness_npcs")) and not self._nearby_npcs(location_id)

        written: list[str] = []
        for npc_id in witnesses:
            memory_text = self._build_memory_text(
                content=content,
                event_type=event_type,
                location_id=location_id,
                game_time=game_time,
                rumor_mode=rumor_mode,
            )
            self.db.execute(
                """INSERT INTO short_term_memories
                   (id, subject_id, type, content, importance, emotional_valence,
                    location, participants, created_at_game_time)
                   VALUES (?, ?, 'player_event', ?, ?, 0.0, ?, ?, ?)""",
                (
                    f"stm_player_event_{uuid.uuid4().hex[:8]}",
                    npc_id,
                    memory_text,
                    importance,
                    location_id,
                    json.dumps(["player", npc_id], ensure_ascii=False),
                    game_time,
                ),
            )
            written.append(npc_id)

        logger.info(
            "[MEMORY] player_event_record type=%s location=%s witnesses=%s importance=%.2f",
            event_type,
            location_id,
            written,
            importance,
        )
        return {"success": True, "written": written, "rumor_mode": rumor_mode}

    def _resolve_witnesses(self, raw_witnesses, location_id: str) -> list[str]:
        """解析见证 NPC；未指定时使用同区/邻区 NPC，仍为空则广播为传闻。"""
        if isinstance(raw_witnesses, list):
            valid = [str(npc_id) for npc_id in raw_witnesses if str(npc_id) in NPC_IDS]
            if valid:
                return sorted(set(valid))

        nearby = self._nearby_npcs(location_id)
        return nearby if nearby else list(NPC_IDS)

    def _nearby_npcs(self, location_id: str) -> list[str]:
        """根据当前 NPC 位置找能看见或听见玩家事件的 NPC。"""
        rows = self.db.fetchall(
            "SELECT npc_id, current_location FROM npc_states WHERE npc_id IN (?, ?, ?, ?, ?)",
            tuple(NPC_IDS),
        )
        return sorted(
            row["npc_id"]
            for row in rows
            if row.get("current_location") and are_nearby(row["current_location"], location_id)
        )

    @staticmethod
    def _build_memory_text(content: str, event_type: str, location_id: str,
                           game_time: str, rumor_mode: bool) -> str:
        """把玩家事件格式化成带时间地点的短期记忆文本。"""
        prefix = "街上传来消息" if rumor_mode else "我注意到"
        return f"[{game_time} @ {location_id}] {prefix}: {content}（玩家事件: {event_type}）"

    @staticmethod
    def _clamp_importance(value) -> float:
        """限制玩家事件重要度范围，避免错误输入污染记忆权重。"""
        try:
            importance = float(value)
        except (TypeError, ValueError):
            importance = 0.7
        return max(0.3, min(1.0, importance))
