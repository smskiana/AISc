"""NPC 日程生成与重规划的安全诊断快照。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from threading import Lock


@dataclass
class ScheduleOwnerTrace:
    """记录单个 owner 的规划阶段、计数和稳定失败原因。"""

    operation_id: str
    npc_id: str
    game_day: int
    status: str = "started"
    candidate_count: int = 0
    selected_count: int = 0
    fallback_seed: int = 0
    elapsed_sec: float = 0.0
    failure_reason: str = ""
    failure_detail: str = ""
    provider_call_not_cancelled: bool = False
    rejection_counts: dict[str, int] = field(default_factory=dict)
    memory_stats: dict[str, int] = field(default_factory=dict)
    fallback_reasons: dict[str, str] = field(default_factory=dict)
    candidate_group_counts: dict[str, int] = field(default_factory=dict)
    evidence_ids: list[str] = field(default_factory=list)
    validation_status: str = "pending"
    execution_phase: str = "candidate_build"


class ScheduleDiagnostics:
    """以 operation ID 保存有界、无 Prompt/LLM 原文的诊断。"""

    def __init__(self, limit: int = 100):
        self._limit = limit
        self._items: dict[str, ScheduleOwnerTrace] = {}
        self._lock = Lock()

    def publish(self, trace: ScheduleOwnerTrace) -> None:
        """原子更新 trace，并淘汰最旧的有界条目。"""
        with self._lock:
            self._items[trace.operation_id] = trace
            while len(self._items) > self._limit:
                self._items.pop(next(iter(self._items)))

    def snapshot(self, operation_id: str = "", npc_id: str = "") -> list[dict]:
        """按 operation 或 NPC 返回安全 DTO。"""
        with self._lock:
            values = list(self._items.values())
        payloads = [asdict(item) for item in values if (not operation_id or item.operation_id.startswith(operation_id)) and (not npc_id or item.npc_id == npc_id)]
        for payload in payloads:
            # 稳定 seed 来自无符号哈希，跨端按十进制字符串传输，避免 Int64/JSON 精度差异。
            payload["fallback_seed"] = str(payload["fallback_seed"])
        return payloads
