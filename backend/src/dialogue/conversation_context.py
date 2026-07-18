"""对话逐轮上下文的数据契约。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ConversationTurn:
    """记录一轮已经实际发生的会话发言。"""

    speaker_id: str
    text: str


@dataclass(frozen=True)
class ImpressionContext:
    """表示说话者对当前对话参与者的关系语境。"""

    target_id: str
    target_name: str
    bond: float
    impression: str


@dataclass(frozen=True)
class RetrievalDiagnostics:
    """保存单轮图检索与向量兜底的结构化诊断。"""

    start_node_ids: list[str] = field(default_factory=list)
    selected_edge_ids: list[str] = field(default_factory=list)
    retrieved_node_ids: list[str] = field(default_factory=list)
    vector_query_preview: str = ""
    vector_fallback_used: bool = False
    failure_reason: str = ""
    retrieval_trace_id: str = ""
    strategy: str = ""
    direction_source: str = ""
    direction: dict = field(default_factory=dict)
    mentions: list[dict] = field(default_factory=list)
    target_anchors: list[dict] = field(default_factory=list)
    layer_stats: list[dict] = field(default_factory=list)
    path_evidence: list[dict] = field(default_factory=list)
    vector_query_count: int = 0
    vector_hit_usage: list[dict] = field(default_factory=list)
    stop_reason: str = ""
    degraded_to_local: bool = False
    policy_summary: dict = field(default_factory=dict)
    retrieval_details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ConversationTurnRequest:
    """描述准备一轮对话上下文所需的稳定输入。"""

    conversation_id: str
    speaker_id: str
    listener_ids: list[str]
    utterance: str
    location_id: str
    game_time: str
    mode: Literal["player_dialogue", "npc_dialogue"]
    history: list[ConversationTurn] = field(default_factory=list)


@dataclass(frozen=True)
class ConversationTurnContext:
    """返回 PromptBuilder 所需的本轮动态关系和记忆上下文。"""

    current_query: str
    conversation_summary: str
    recent_turns: list[ConversationTurn]
    participant_impressions: list[ImpressionContext]
    retrieved_memories: str
    retrieval_diagnostics: RetrievalDiagnostics
