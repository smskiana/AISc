"""玩家快捷回复建议的安全摘要诊断。"""
from __future__ import annotations

import uuid
from threading import Lock
from typing import Any


class ReplySuggestionTraceStore:
    """保留固定容量的快捷回复安全摘要，不保存完整 Prompt 或原始输出。"""

    def __init__(self, capacity: int = 100, preview_limit: int = 24):
        """创建有界 trace 缓存和预览长度限制。"""
        self.capacity = max(1, int(capacity))
        self.preview_limit = max(1, int(preview_limit))
        self._items: list[dict[str, Any]] = []
        self._lock = Lock()

    def record(
        self,
        *,
        npc_id: str,
        player_id: str,
        context_keys: list[str],
        choices: list[str],
        rejected_choices: list[dict[str, str]],
        fallback_used: bool,
        failure_reason: str,
        elapsed_ms: int,
    ) -> str:
        """追加一条最小安全摘要并返回稳定 trace ID。"""
        trace_id = f"reply_{uuid.uuid4().hex[:12]}"
        payload = {
            "reply_trace_id": trace_id,
            "npc_id": str(npc_id or ""),
            "player_id": str(player_id or ""),
            "task_id": "player_reply_suggestions",
            "speaker_role_expected": "player",
            "recipient_role_expected": "npc",
            "context_keys": sorted(str(key) for key in context_keys),
            "choice_count": len(choices),
            "choice_previews": [self._preview(choice) for choice in choices],
            "rejected_choice_previews": [self._preview(item.get("choice", "")) for item in rejected_choices],
            "rejection_reasons": [str(item.get("reason", "")) for item in rejected_choices],
            "fallback_used": bool(fallback_used),
            "failure_reason": str(failure_reason or ""),
            "elapsed_ms": max(0, int(elapsed_ms)),
        }
        with self._lock:
            self._items.append(payload)
            del self._items[:-self.capacity]
        return trace_id

    def snapshot(self, reply_trace_id: str | None = None, npc_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """按 trace 或 NPC 筛选安全摘要，并优先返回最近记录。"""
        with self._lock:
            items = list(self._items)
        result: list[dict[str, Any]] = []
        for item in reversed(items):
            if reply_trace_id and item["reply_trace_id"] != reply_trace_id:
                continue
            if npc_id and item["npc_id"] != npc_id:
                continue
            result.append(dict(item))
            if len(result) >= max(1, min(int(limit), self.capacity)):
                break
        return result

    def _preview(self, text: str) -> str:
        """裁剪诊断文本预览，避免 trace 保存完整业务内容。"""
        compact = " ".join(str(text or "").split())
        if len(compact) <= self.preview_limit:
            return compact
        return compact[:self.preview_limit].rstrip() + "..."


reply_suggestion_trace_store = ReplySuggestionTraceStore()
