"""活跃对话的会话级工作记忆与逐轮检索编排。"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..memory.retrieval import RetrievalRequest
from .conversation_context import (
    ConversationTurn,
    ConversationTurnContext,
    ConversationTurnRequest,
    ImpressionContext,
    RetrievalDiagnostics,
)


@dataclass
class ConversationWorkingMemory:
    """保存活跃会话的近期原文和滚动摘要。"""

    conversation_id: str
    participant_ids: list[str]
    turns: list[ConversationTurn] = field(default_factory=list)
    rolling_summary: str = ""
    started_game_time: str = ""

    def append_turn(self, turn: ConversationTurn, recent_limit: int = 8) -> None:
        """追加有效发言，并将超出窗口的旧轮次压入确定性滚动摘要。"""
        self.turns.append(turn)
        if len(self.turns) <= recent_limit:
            return
        overflow = self.turns[:-recent_limit]
        self.turns = self.turns[-recent_limit:]
        summary_part = " | ".join(f"{turn.speaker_id}: {turn.text[:80]}" for turn in overflow)
        self.rolling_summary = " | ".join(part for part in (self.rolling_summary, summary_part) if part)[-800:]


class ConversationMemoryCoordinator:
    """统一管理逐轮工作记忆、参与者关系和记忆检索。"""

    def __init__(self, db, retrieval):
        """注入数据库和结构化检索引擎。"""
        self.db = db
        self.retrieval = retrieval
        self._sessions: dict[str, ConversationWorkingMemory] = {}
        self._diagnostics: dict[tuple[str, str], ConversationTurnContext] = {}
        self._diagnostic_modes: dict[tuple[str, str], str] = {}

    def start(self, conversation_id: str, participant_ids: list[str], game_time: str) -> ConversationWorkingMemory:
        """建立或返回指定活跃会话的工作记忆。"""
        memory = self._sessions.get(conversation_id)
        if memory is None:
            memory = ConversationWorkingMemory(conversation_id, list(participant_ids), started_game_time=game_time)
            self._sessions[conversation_id] = memory
        return memory

    def append_turn(self, conversation_id: str, turn: ConversationTurn) -> None:
        """仅把已经有效发生的发言追加到活跃会话。"""
        memory = self._sessions.get(conversation_id)
        if memory is None:
            memory = self.start(conversation_id, [turn.speaker_id], "")
        memory.append_turn(turn)

    def prepare_turn_context(self, request: ConversationTurnRequest) -> ConversationTurnContext:
        """为当前说话者生成参与者关系、图路由和向量兜底上下文。"""
        memory = self.start(
            request.conversation_id,
            [request.speaker_id, *request.listener_ids],
            request.game_time,
        )
        history = request.history or memory.turns
        participants = [self._get_impression(request.speaker_id, target_id) for target_id in request.listener_ids]
        retrieval_result = self.retrieval.retrieve(RetrievalRequest(
            npc_id=request.speaker_id,
            conversation_participant_ids=list(request.listener_ids),
            query_text=request.utterance,
            conversation_summary=memory.rolling_summary,
            recent_turns=list(history[-8:]),
            location_id=request.location_id,
            game_time=request.game_time,
            mode=request.mode,
        ))
        context = ConversationTurnContext(
            current_query=request.utterance,
            conversation_summary=memory.rolling_summary,
            recent_turns=list(history[-8:]),
            participant_impressions=participants,
            retrieved_memories=retrieval_result.rebuilt_context,
            retrieval_diagnostics=RetrievalDiagnostics(
                start_node_ids=retrieval_result.start_node_ids,
                selected_edge_ids=retrieval_result.selected_edge_ids,
                retrieved_node_ids=retrieval_result.retrieved_node_ids,
                vector_query_preview=retrieval_result.vector_query_preview,
                vector_fallback_used=retrieval_result.fallback_used,
                failure_reason=retrieval_result.diagnostics.get("failure_reason", ""),
                retrieval_trace_id=retrieval_result.diagnostics.get("retrieval_trace_id", ""),
                strategy=retrieval_result.diagnostics.get("strategy", ""),
                direction_source=retrieval_result.diagnostics.get("direction_source", ""),
                direction=retrieval_result.diagnostics.get("direction", {}),
                mentions=retrieval_result.diagnostics.get("mentions", []),
                target_anchors=retrieval_result.diagnostics.get("target_anchors", []),
                layer_stats=retrieval_result.diagnostics.get("layer_stats", []),
                path_evidence=retrieval_result.diagnostics.get("path_evidence", []),
                vector_query_count=int(retrieval_result.diagnostics.get("vector_query_count", 0)),
                vector_hit_usage=retrieval_result.diagnostics.get("vector_hit_usage", []),
                stop_reason=retrieval_result.diagnostics.get("stop_reason", ""),
                degraded_to_local=bool(retrieval_result.diagnostics.get("degraded_to_local", False)),
                policy_summary=retrieval_result.diagnostics.get("policy_summary", {}),
                retrieval_details={
                    key: value for key, value in retrieval_result.diagnostics.items()
                    if key in {"original_query_preview", "original_query_chars", "retrieval_query_preview", "retrieval_query_chars", "retrieval_query_source", "query_constraints", "selected_recent_turn_preview", "selected_recent_turn_chars", "selection_reason", "embedding_query_preview", "embedding_query_chars", "direction_validation_errors", "direction_calibrations", "query_fallback_reason", "graph_candidate_ids", "final_entries", "evicted_entries", "final_entry_count", "final_context_chars"}
                },
            ),
        )
        self._diagnostics[(request.conversation_id, request.speaker_id)] = context
        self._diagnostic_modes[(request.conversation_id, request.speaker_id)] = request.mode
        return context

    def release(self, conversation_id: str) -> None:
        """释放终态或失败会话，避免工作记忆污染后续对话。"""
        self._sessions.pop(conversation_id, None)
        stale = [key for key in self._diagnostics if key[0] == conversation_id]
        for key in stale:
            self._diagnostics.pop(key, None)
            self._diagnostic_modes.pop(key, None)

    def reset(self) -> None:
        """在断线或读档时清空全部不可持久恢复的活跃会话状态。"""
        self._sessions.clear()
        self._diagnostics.clear()
        self._diagnostic_modes.clear()

    def diagnostic_snapshot(self) -> list[dict]:
        """返回可序列化的活跃会话逐轮检索快照。"""
        snapshots: list[dict] = []
        for conversation_id, memory in self._sessions.items():
            for (diag_conversation_id, speaker_id), context in self._diagnostics.items():
                if diag_conversation_id != conversation_id:
                    continue
                snapshot = {
                    "conversation_id": conversation_id,
                    "mode": self._diagnostic_modes.get((conversation_id, speaker_id), ""),
                    "speaker_id": speaker_id,
                    "participant_ids": memory.participant_ids,
                    "current_utterance": context.current_query,
                    "recent_dialogue_preview": [
                        f"{turn.speaker_id}: {turn.text[:120]}" for turn in context.recent_turns[-8:]
                    ],
                    "participant_impressions": [
                        f"{item.target_id}|bond={item.bond:.2f}|{item.impression}"
                        for item in context.participant_impressions
                    ],
                    "start_node_ids": context.retrieval_diagnostics.start_node_ids,
                    "selected_edge_ids": context.retrieval_diagnostics.selected_edge_ids,
                    "retrieved_node_ids": context.retrieval_diagnostics.retrieved_node_ids,
                    "vector_query_preview": context.retrieval_diagnostics.vector_query_preview,
                    "vector_fallback_used": context.retrieval_diagnostics.vector_fallback_used,
                    "working_memory_turn_count": len(memory.turns),
                    "rolling_summary_preview": memory.rolling_summary[:240],
                    "persistence_status": "working_memory_only",
                    "failure_reason": context.retrieval_diagnostics.failure_reason,
                    "retrieval_trace_id": context.retrieval_diagnostics.retrieval_trace_id,
                    "strategy": context.retrieval_diagnostics.strategy,
                    "direction_source": context.retrieval_diagnostics.direction_source,
                    "direction": context.retrieval_diagnostics.direction,
                    "mentions": context.retrieval_diagnostics.mentions,
                    "target_anchors": context.retrieval_diagnostics.target_anchors,
                    "layer_stats": context.retrieval_diagnostics.layer_stats,
                    "path_evidence": context.retrieval_diagnostics.path_evidence,
                    "vector_query_count": context.retrieval_diagnostics.vector_query_count,
                    "vector_hit_usage": context.retrieval_diagnostics.vector_hit_usage,
                    "stop_reason": context.retrieval_diagnostics.stop_reason,
                    "degraded_to_local": context.retrieval_diagnostics.degraded_to_local,
                    "policy_summary": context.retrieval_diagnostics.policy_summary,
                }
                snapshot.update(context.retrieval_diagnostics.retrieval_details)
                snapshots.append(snapshot)
        return snapshots

    def get_diagnostic(self, conversation_id: str, speaker_id: str) -> dict:
        """返回指定会话和说话者的最新诊断消息载荷。"""
        return next(
            (
                item for item in self.diagnostic_snapshot()
                if item["conversation_id"] == conversation_id and item["speaker_id"] == speaker_id
            ),
            {},
        )

    def _get_impression(self, owner_id: str, target_id: str) -> ImpressionContext:
        """读取当前对话参与者的 bond 和印象文本。"""
        impression_row = self.db.fetchone(
            "SELECT baseline_impression, delta_note FROM npc_impressions WHERE owner_id=? AND target_id=?",
            (owner_id, target_id),
        ) or {}
        bond_row = self.db.fetchone(
            "SELECT bond FROM npc_bonds WHERE owner_id=? AND target_id=?",
            (owner_id, target_id),
        ) or {}
        impression = "；".join(
            str(impression_row.get(key) or "").strip()
            for key in ("baseline_impression", "delta_note")
        )
        return ImpressionContext(
            target_id,
            target_id,
            float(bond_row.get("bond", 0.0) or 0.0),
            impression or "暂无特别判断",
        )
