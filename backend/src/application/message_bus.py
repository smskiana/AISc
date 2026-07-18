"""消息总线：统一管理当前连接与轮询队列。"""
from __future__ import annotations

import collections
from datetime import datetime
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("sakurabashi.message_bus")


class MessageBus:
    """WS 直推 + HTTP 轮询双写消息总线。"""

    def __init__(self):
        self._queue: collections.deque = collections.deque()
        self._active_ws: Any | None = None
        self._poll_queue_enabled = os.getenv("SAKURA_ENABLE_POLL_QUEUE", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._unity_log_path = log_dir / "unity_messages.log"
        logger.info("[WS] poll_queue_enabled=%s", int(self._poll_queue_enabled))

    @property
    def active_ws(self) -> Any | None:
        return self._active_ws

    def attach(self, ws: Any) -> None:
        self._active_ws = ws

    def detach(self, ws: Any | None = None) -> None:
        if ws is None or self._active_ws is ws:
            self._active_ws = None

    async def send_to_active(self, payload: dict) -> None:
        """只向当前连接发送，不入轮询队列。"""
        delivered = False
        if self._active_ws:
            try:
                await self._active_ws.send_json(payload)
                delivered = True
            except Exception:
                pass
        self._persist_visual_message(payload, delivered=delivered, source="active")
        if not delivered:
            self._log_without_receiver(payload)

    async def broadcast(self, payload: dict) -> None:
        """广播到当前 WebSocket；轮询队列默认关闭，仅保留调试开关。"""
        if self._poll_queue_enabled:
            self._queue.append(payload)
        delivered = False
        if self._active_ws:
            try:
                await self._active_ws.send_json(payload)
                delivered = True
            except Exception:
                pass
        self._persist_visual_message(payload, delivered=delivered, source="broadcast")
        if not delivered:
            self._log_without_receiver(payload)

    def drain(self) -> list[dict]:
        """返回所有积压消息并清空。"""
        batch = []
        while self._queue:
            batch.append(self._queue.popleft())
        return batch

    def _log_without_receiver(self, payload: dict) -> None:
        """没有 Unity/C# 接收时，将关键可视化消息写入后端日志。"""
        msg_type = payload.get("type", "")

        if msg_type == "NPC_BUBBLE":
            npc_id = payload.get("npc_id", "?")
            target_id = payload.get("target_npc_id", "?")
            text = str(payload.get("text", "")).strip()
            logger.info(f"[无C#接收] NPC_BUBBLE {npc_id} -> {target_id}: {text}")
            return

        if msg_type == "NPC_SOCIAL_ACTION":
            npc_a = payload.get("npc_id", "?")
            npc_b = payload.get("target_npc_id", "?")
            location = payload.get("location_id", "?")
            reason = payload.get("reason", "")
            logger.info(f"[无C#接收] NPC_SOCIAL_ACTION {npc_a} <-> {npc_b} @ {location} ({reason})")
            return

    def _persist_visual_message(self, payload: dict, delivered: bool, source: str) -> None:
        """将 Unity 关键消息单独写入 UTF-8 日志，便于跑测后复盘。"""
        msg_type = payload.get("type", "")
        if msg_type not in {"NPC_BUBBLE", "NPC_SOCIAL_ACTION"}:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        delivery = "live" if delivered else "fallback"

        if msg_type == "NPC_BUBBLE":
            line = (
                f"{timestamp} [{delivery}] [{source}] NPC_BUBBLE "
                f"{payload.get('npc_id', '?')} -> {payload.get('target_npc_id', '?')}: "
                f"{str(payload.get('text', '')).strip()}"
            )
        else:
            line = (
                f"{timestamp} [{delivery}] [{source}] NPC_SOCIAL_ACTION "
                f"{payload.get('npc_id', '?')} <-> {payload.get('target_npc_id', '?')} "
                f"@ {payload.get('location_id', '?')} ({payload.get('reason', '')})"
            )

        try:
            with self._unity_log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            logger.debug(f"Unity 消息日志写入失败: {e}")
