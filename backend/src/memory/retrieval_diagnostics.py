"""记忆检索 trace 的安全摘要存储和筛选。"""
from __future__ import annotations

from dataclasses import asdict
from threading import Lock
from typing import Any

from .retrieval_contracts import RetrievalTrace


class RetrievalTraceStore:
    """保留固定容量的最近检索 trace，不保存完整 Prompt 或原始 LLM 输出。"""

    def __init__(self, capacity: int = 100):
        """创建有界 trace 缓存。"""
        self.capacity = max(1, int(capacity))
        self._items: list[RetrievalTrace] = []
        self._lock = Lock()

    def add(self, trace: RetrievalTrace) -> None:
        """追加一条 trace 并淘汰最旧记录。"""
        with self._lock:
            self._items.append(trace)
            del self._items[:-self.capacity]

    def snapshot(self, trace_id: str | None = None, npc_id: str | None = None, mode: str | None = None, strategy: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """按稳定过滤字段返回安全字典。"""
        with self._lock:
            items = list(self._items)
        result = []
        for item in reversed(items):
            if trace_id and item.retrieval_trace_id != trace_id:
                continue
            if npc_id and item.npc_id != npc_id:
                continue
            if mode and item.mode != mode:
                continue
            if strategy and item.strategy != strategy:
                continue
            payload = asdict(item)
            # Unity DTO 使用扁平安全字段；内部 diagnostics 不作为跨端动态字典契约。
            payload.update(payload.pop("diagnostics", {}))
            result.append(payload)
            if len(result) >= max(1, min(int(limit), self.capacity)):
                break
        return result


retrieval_trace_store = RetrievalTraceStore()
