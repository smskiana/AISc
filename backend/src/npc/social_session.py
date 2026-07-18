"""Unity 权威 NPC-NPC 社交会话的内容生成与完成提交。"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Awaitable, Callable

from ..application.operation_context import GameTimeSnapshot


class NpcSocialContentService:
    """只缓存语义内容，绝不创建、取消或监督 Unity 运行时会话。"""

    def __init__(
        self,
        dialogue_manager,
        completion_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        cache_limit: int = 100,
    ):
        """绑定内容生成器与有效 COMPLETE 后的重规划回调。"""
        self.dialogue_manager = dialogue_manager
        self.completion_callback = completion_callback
        self.cache_limit = cache_limit
        self._prepared: OrderedDict[str, dict[str, Any]] = OrderedDict()

    async def handle_content_request(self, msg: dict) -> dict:
        """按 Unity session ID 幂等生成结构化对白内容。"""
        request_id = str(msg.get("request_id") or "")
        npc_a = str(msg.get("npc_id") or "")
        npc_b = str(msg.get("target_npc_id") or "")
        if not all((request_id, npc_a, npc_b)):
            raise ValueError("social_content_identity_missing")
        existing = self._prepared.get(request_id)
        if existing is not None:
            return dict(existing["result"])
        game_time = GameTimeSnapshot.from_dict(msg.get("game_time") or {})
        location = str(msg.get("actual_location_id") or msg.get("location_id") or "")
        lines = await self.dialogue_manager.generate_prepared_social(
            request_id, npc_a, npc_b, location, self._format_time(game_time)
        )
        result = {
            "type": "NPC_SOCIAL_CONTENT_RESULT",
            "request_id": request_id,
            "candidate_id": str(msg.get("candidate_id") or ""),
            "npc_id": npc_a,
            "target_npc_id": npc_b,
            "world_revision": int(msg.get("world_revision") or 0),
            "success": bool(lines),
            "reason": "" if lines else "empty_content",
            "lines": [
                {
                    "speaker_npc_id": speaker_id,
                    "target_npc_id": npc_b if speaker_id == npc_a else npc_a,
                    "text": text,
                    "duration_sec": round(max(2.0, len(text) * 0.15), 1),
                }
                for speaker_id, text in lines
            ],
        }
        self._prepared[request_id] = {
            "result": result,
            "npc_a": npc_a,
            "npc_b": npc_b,
            "location": location,
            "game_time": self._format_time(game_time),
            "lines": lines,
            "base_world_revision": int(msg.get("world_revision") or 0),
        }
        while len(self._prepared) > self.cache_limit:
            self._prepared.popitem(last=False)
        return dict(result)

    async def handle_complete(self, msg: dict) -> dict:
        """仅提交与已生成内容、参与者及 revision 匹配的 Unity COMPLETE。"""
        request_id = str(msg.get("request_id") or "")
        prepared = self._prepared.get(request_id)
        if prepared is None:
            return {"accepted": False, "reason": "stale_or_unknown_request"}
        participants = {str(msg.get("npc_id") or ""), str(msg.get("target_npc_id") or "")}
        if participants != {prepared["npc_a"], prepared["npc_b"]}:
            return {"accepted": False, "reason": "participant_mismatch"}
        world_revision = int(msg.get("world_revision") or 0)
        if world_revision < int(prepared["base_world_revision"]):
            return {"accepted": False, "reason": "stale_world_revision"}
        commit_result = self.dialogue_manager.commit_prepared_social(
            prepared["npc_a"], prepared["npc_b"], prepared["lines"],
            str(msg.get("actual_location_id") or prepared["location"]),
            prepared["game_time"], base_world_revision=world_revision,
            operation_id=request_id,
        )
        self._prepared.pop(request_id, None)
        context = {
            "operation_id": request_id,
            "npc_ids": [prepared["npc_a"], prepared["npc_b"]],
            "participant_ids": [prepared["npc_a"], prepared["npc_b"]],
            "interaction_type": "npc_dialogue",
            "end_reason": "completed",
            "interaction_summary": commit_result.get("summary", ""),
            "location_id": str(msg.get("actual_location_id") or prepared["location"]),
            "state_effects": list(commit_result.get("effects") or []),
            "base_world_revision": world_revision,
            "game_time": msg.get("game_time") or {},
        }
        if self.completion_callback is not None and context["interaction_summary"]:
            await self.completion_callback(context)
        return {"accepted": True, "status": "completed"}

    def discard(self, msg: dict) -> dict:
        """丢弃 Unity 已终止 session 的未提交语义内容。"""
        request_id = str(msg.get("request_id") or "")
        existed = self._prepared.pop(request_id, None) is not None
        return {"accepted": existed, "status": "discarded"}

    def reset(self) -> None:
        """连接重置时清除未提交内容，不向 Unity 发取消命令。"""
        self._prepared.clear()

    @staticmethod
    def _format_time(game_time: GameTimeSnapshot) -> str:
        """将冻结快照格式化为现有 Prompt 与记忆使用的时间文本。"""
        return f"第{game_time.day}天 {game_time.hour:02d}:{game_time.minute:02d}"
