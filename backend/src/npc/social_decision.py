"""Unity 候选驱动的 NPC-NPC 社交语义决策。"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from typing import Awaitable, Callable

from ..application.operation_context import GameTimeSnapshot


@dataclass(frozen=True)
class SocialDecisionRequest:
    """保存 Unity 已确认物理候选的冻结输入。"""

    request_id: str
    candidate_id: str
    npc_id: str
    target_npc_id: str
    location_id: str
    world_revision: int
    game_time: GameTimeSnapshot


class NpcSocialDecisionService:
    """只负责关系、记忆和 LLM 意愿，不持有物理候选或冷却。"""

    def __init__(self, decide: Callable[[SocialDecisionRequest], Awaitable[tuple[bool, str, str]]], cache_limit: int = 100):
        self._decide = decide
        self._cache_limit = cache_limit
        self._results: OrderedDict[str, dict] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}

    async def decide(self, payload: dict) -> dict:
        """按 request ID 幂等执行语义决策并返回输入 revision。"""
        request = self._parse(payload)
        existing = self._results.get(request.request_id)
        if existing is not None:
            return dict(existing)
        lock = self._locks.setdefault(request.request_id, asyncio.Lock())
        async with lock:
            existing = self._results.get(request.request_id)
            if existing is not None:
                return dict(existing)
            try:
                want_to_talk, reason, opening_intent = await self._decide(request)
                result = self._result(request, want_to_talk, reason, opening_intent)
            except Exception:
                result = self._result(request, False, "social_decision_unavailable", "")
            self._results[request.request_id] = result
            while len(self._results) > self._cache_limit:
                self._results.popitem(last=False)
            self._locks.pop(request.request_id, None)
            return dict(result)

    @staticmethod
    def _parse(payload: dict) -> SocialDecisionRequest:
        """严格解析关联 ID、版本和冻结时间。"""
        request_id = str(payload.get("request_id") or "")
        candidate_id = str(payload.get("candidate_id") or "")
        npc_id = str(payload.get("npc_id") or "")
        target_id = str(payload.get("target_npc_id") or "")
        if not all((request_id, candidate_id, npc_id, target_id)):
            raise ValueError("social_decision_identity_missing")
        return SocialDecisionRequest(
            request_id=request_id,
            candidate_id=candidate_id,
            npc_id=npc_id,
            target_npc_id=target_id,
            location_id=str(payload.get("location_id") or ""),
            world_revision=int(payload.get("world_revision", -1)),
            game_time=GameTimeSnapshot.from_dict(payload.get("game_time") or {}),
        )

    @staticmethod
    def _result(request: SocialDecisionRequest, want: bool, reason: str, opening: str) -> dict:
        """构造稳定 snake_case result DTO。"""
        return {
            "type": "NPC_SOCIAL_DECISION_RESULT",
            "request_id": request.request_id,
            "candidate_id": request.candidate_id,
            "npc_id": request.npc_id,
            "target_npc_id": request.target_npc_id,
            "world_revision": request.world_revision,
            "want_to_talk": bool(want),
            "reason": reason or "",
            "opening_intent": opening or "",
        }
