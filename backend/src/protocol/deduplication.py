"""有限容量的请求幂等结果缓存。"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from typing import Any


class RequestDeduplicator:
    """按 request_id 保存已提交副作用命令的响应。"""

    def __init__(self, capacity: int = 512):
        """创建指定容量的最近使用结果缓存。"""
        self.capacity = max(1, capacity)
        self._results: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def get(self, request_id: str) -> dict[str, Any] | None:
        """返回缓存结果副本，并刷新最近使用顺序。"""
        if not request_id or request_id not in self._results:
            return None
        self._results.move_to_end(request_id)
        return deepcopy(self._results[request_id])

    def remember(self, request_id: str, result: dict[str, Any]) -> None:
        """记录请求结果，并淘汰最早条目。"""
        if not request_id:
            return
        self._results[request_id] = deepcopy(result)
        self._results.move_to_end(request_id)
        while len(self._results) > self.capacity:
            self._results.popitem(last=False)
