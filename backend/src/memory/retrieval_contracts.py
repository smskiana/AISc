"""记忆检索的稳定数据契约、受控枚举和策略 DTO。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class _StringEnum(str, Enum):
    """提供可直接序列化的字符串枚举基类。"""

    def __str__(self) -> str:
        """返回配置和诊断使用的稳定枚举值。"""
        return self.value


class RetrievalStrategy(_StringEnum):
    """公开的三种记忆路由策略。"""

    LOCAL_ONLY = "local_only"
    LLM_GUIDED_LOCAL = "llm_guided_local"
    LLM_FULL_ROUTE = "llm_full_route"


class Theme(_StringEnum):
    """方向主题白名单。"""

    IDENTITY = "identity"
    CURRENT_LOCATION = "current_location"
    RECENT_ACTIVITY = "recent_activity"
    RELATIONSHIP = "relationship"
    CAUSE = "cause"
    PAST_EVENT = "past_event"
    EMOTION = "emotion"
    OBJECT = "object"
    PROMISE = "promise"
    GENERAL = "general"


class RelationFacet(_StringEnum):
    """关系维度白名单。"""

    FAMILIARITY = "familiarity"
    AFFINITY = "affinity"
    OCCUPATION = "occupation"
    SHARED_EVENT = "shared_event"
    IMPRESSION_BASIS = "impression_basis"
    KNOWLEDGE_SOURCE = "knowledge_source"


class TimeScope(_StringEnum):
    """时间方向白名单。"""

    CURRENT = "current"
    RECENT = "recent"
    PAST = "past"
    ANY = "any"


class SourcePreference(_StringEnum):
    """记忆来源偏好白名单。"""

    DIRECT = "direct"
    HEARD = "heard"
    INFERRED = "inferred"


class RecallIntent(_StringEnum):
    """回忆意图白名单。"""

    LOCATE_PERSON = "locate_person"
    IDENTIFY_ENTITY = "identify_entity"
    EXPLAIN_CAUSE = "explain_cause"
    COMPARE_RELATIONSHIP = "compare_relationship"
    RECALL_EVENT = "recall_event"
    CONTINUE_REFERENCE = "continue_reference"
    GENERAL_RECALL = "general_recall"


class QueryConstraint(_StringEnum):
    """检索想法允许携带的最小语义约束。"""

    PERSON_LOCATION = "person_location"
    IDENTITY = "identity"
    RELATIONSHIP = "relationship"
    CAUSE = "cause"
    PAST_EVENT = "past_event"
    RECENT = "recent"


class NegativeDirection(_StringEnum):
    """需要主动降权的方向白名单。"""

    UNRELATED_PLAYER_BACKGROUND = "unrelated_player_background"
    UNRELATED_PRIVATE_MEMORY = "unrelated_private_memory"
    STALE_LOCATION = "stale_location"
    UNRELATED_PERSON = "unrelated_person"


class StopReason(_StringEnum):
    """搜索结束原因。"""

    SUFFICIENT_EVIDENCE = "sufficient_evidence"
    FRONTIER_EXHAUSTED = "frontier_exhausted"
    DEPTH_LIMIT_REACHED = "depth_limit_reached"
    EDGE_BUDGET_EXHAUSTED = "edge_budget_exhausted"
    EARLY_STOP_MARGIN_REACHED = "early_stop_margin_reached"


class FailureReason(_StringEnum):
    """无法形成可用结果的原因。"""

    NONE = "none"
    START_NODES_NOT_FOUND = "start_nodes_not_found"
    NO_REACHABLE_PATH = "no_reachable_path"
    KNOWLEDGE_ABSENT = "knowledge_absent"
    KNOWLEDGE_FORBIDDEN = "knowledge_forbidden"
    DIRECTION_PARSE_FAILED = "direction_parse_failed"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    BUDGET_EXHAUSTED = "budget_exhausted"


@dataclass(frozen=True)
class RetrievalRequest:
    """描述一次逐轮图路由和向量兜底所需的完整语义输入。"""

    npc_id: str
    conversation_participant_ids: list[str] = field(default_factory=list)
    query_text: str = ""
    conversation_summary: str = ""
    recent_turns: list[Any] = field(default_factory=list)
    location_id: str = ""
    game_time: str = ""
    mode: str = "player_dialogue"
    direction_override: RetrievalDirection | None = None
    direction_source: str = ""


@dataclass(frozen=True)
class RetrievalResult:
    """返回重建上下文以及可供诊断和测试断言的检索证据。"""

    rebuilt_context: str = ""
    start_node_ids: list[str] = field(default_factory=list)
    selected_edge_ids: list[str] = field(default_factory=list)
    retrieved_node_ids: list[str] = field(default_factory=list)
    vector_query_preview: str = ""
    fallback_used: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedMention:
    """记录自然语言 mention 是否解析到稳定实体。"""

    text: str
    entity_id: str = ""
    entity_type: str = ""
    source: str = "query"
    confidence: float = 0.0


@dataclass(frozen=True)
class RetrievalDirection:
    """方向解析的受控结果，不允许携带节点或边 ID。"""

    entity_mentions: list[str] = field(default_factory=list)
    location_mentions: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=lambda: [Theme.GENERAL.value])
    relation_facets: list[str] = field(default_factory=list)
    time_scope: str = TimeScope.ANY.value
    source_preferences: list[str] = field(default_factory=list)
    recall_intent: str = RecallIntent.GENERAL_RECALL.value
    negative_directions: list[str] = field(default_factory=list)
    retrieval_query: str = ""
    query_constraints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DirectionResolution:
    """统一封装方向、mention 解析、来源和校验诊断。"""

    direction: RetrievalDirection
    mentions: list[ResolvedMention] = field(default_factory=list)
    source: str = "local"
    failure_reason: str = ""
    validation_errors: list[str] = field(default_factory=list)
    calibrations: list[str] = field(default_factory=list)
    llm_output_summary: str = ""
    provider_diagnostics: DirectionProviderDiagnostics | None = None


@dataclass(frozen=True)
class DirectionProviderAttempt:
    """记录一次方向 provider 尝试的安全、有界结果。"""
    provider_id: str
    status: str
    failure_reason: str = ""
    elapsed_ms: int = 0
    queue_ms: int = 0
    model_call_count: int = 0


@dataclass(frozen=True)
class DirectionProviderDiagnostics:
    """记录冻结 provider chain 的采用结果和模型身份。"""
    requested_provider: str = ""
    adopted_provider: str = ""
    chain: tuple[str, ...] = ()
    attempts: tuple[DirectionProviderAttempt, ...] = ()
    model_id: str = ""
    model_revision: str = ""
    adapter_id: str = ""
    schema_version: int = 1
    worker_state: str = "not_applicable"

    @property
    def model_call_count(self) -> int:
        """汇总 chain 内实际发出的方向模型调用次数。"""
        return sum(item.model_call_count for item in self.attempts)

    @property
    def fallback_reasons(self) -> tuple[str, ...]:
        """按尝试顺序返回稳定失败原因。"""
        return tuple(item.failure_reason for item in self.attempts if item.failure_reason)


@dataclass(frozen=True)
class SearchBudget:
    """一次本地深搜的硬预算。"""

    max_depth: int
    beam_width: int
    max_neighbors_per_node: int
    max_expanded_edges: int
    max_anchor_count: int
    max_answer_candidates: int
    min_path_score: float
    early_stop_margin: float


@dataclass(frozen=True)
class LocalSearchPolicy:
    """本地深搜参数。"""

    budget: SearchBudget


@dataclass(frozen=True)
class LlmRoutePolicy:
    """完全 LLM 路由参数。"""

    max_hops: int
    max_frontier_nodes: int
    max_neighbors_per_node: int
    max_candidate_edges: int
    selected_edges_per_hop: int
    max_llm_route_calls: int
    candidate_summary_chars: int
    max_route_prompt_chars: int


@dataclass(frozen=True)
class RetrievalExecutionOptions:
    """共享输入、向量和最终结果预算。"""

    recent_turn_limit: int
    recent_memory_limit: int
    memory_summary_chars: int
    conversation_summary_chars: int
    max_direction_context_chars: int
    vector_search_top_k: int
    vector_fallback_limit: int
    final_memory_limit: int
    retrieval_query_chars: int
    selected_recent_turn_limit: int
    selected_recent_turn_chars: int
    embedding_query_chars: int
    final_context_max_chars: int


@dataclass(frozen=True)
class RetrievalModePolicy:
    """一个业务模式的完整不可变策略。"""

    mode: str
    strategy: RetrievalStrategy
    context: RetrievalExecutionOptions
    local_search: LocalSearchPolicy
    llm_route: LlmRoutePolicy
    scoring: dict[str, float]
    final_scoring: dict[str, float]
    direction_chain: tuple[str, ...] = ("local",)
    version: int = 2


@dataclass(frozen=True)
class DirectionProviderConfig:
    """一个已严格校验的方向 provider 配置。"""
    provider_id: str
    kind: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DirectionProviderRegistryConfig:
    """方向 provider 注册表及默认冻结 chain。"""
    default_chain: tuple[str, ...]
    providers: dict[str, DirectionProviderConfig]


@dataclass(frozen=True)
class SearchPathEvidence:
    """一条实际被采用的路径证据。"""

    node_id: str
    edge_id: str
    from_node_id: str
    direction: str
    score: float
    score_components: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class VectorSearchHit:
    """向量 adapter 归一化后的单次 ANN 命中。"""

    node_id: str
    rank: int
    similarity: float
    usage: str = ""


@dataclass(frozen=True)
class RetrievalQueryPlan:
    """单次 embedding 查询的可诊断纯函数输出。"""

    original_query: str
    retrieval_query: str
    retrieval_query_source: str
    query_constraints: list[str]
    explicit_entities: list[str]
    selected_recent_turn: str = ""
    selection_reason: str = "none"
    embedding_query: str = ""
    fallback_reason: str = ""
    original_query_exceeds_budget: bool = False


@dataclass(frozen=True)
class RetrievedMemoryEntry:
    """不可拆分的最终记忆条目及其六分量评分。"""

    node_id: str
    node_type: str
    rendered_text: str
    score: float
    score_components: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalContextAssembly:
    """最终条目、字符预算结果和淘汰原因。"""

    entries: list[RetrievedMemoryEntry] = field(default_factory=list)
    evicted_entries: list[dict[str, str]] = field(default_factory=list)
    context_text: str = ""
    failure_reason: str = FailureReason.NONE.value


@dataclass(frozen=True)
class DeepSearchRequest:
    """DirectedDeepRetriever 的唯一输入 seam。"""

    npc_id: str
    target_id: str
    start_node_ids: list[str]
    target_start_id: str | None
    direction: RetrievalDirection
    policy: LocalSearchPolicy
    vector_anchor_ids: list[str] = field(default_factory=list)
    side_effects_disabled: bool = False


@dataclass(frozen=True)
class DeepSearchOutcome:
    """本地深搜输出及逐层统计。"""

    node_ids: list[str] = field(default_factory=list)
    selected_edges: list[dict[str, Any]] = field(default_factory=list)
    path_evidence: list[SearchPathEvidence] = field(default_factory=list)
    candidate_edges: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = StopReason.FRONTIER_EXHAUSTED.value
    failure_reason: str = FailureReason.NONE.value
    layer_stats: list[dict[str, int]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class LlmGraphSearchRequest:
    """LlmGraphRetriever 的唯一输入 seam。"""

    npc_id: str
    target_id: str
    start_node_ids: list[str]
    route_context: dict[str, Any]
    policy: LlmRoutePolicy
    side_effects_disabled: bool = False


@dataclass(frozen=True)
class LlmGraphSearchOutcome:
    """完全 LLM 路由输出。"""

    node_ids: list[str] = field(default_factory=list)
    selected_edges: list[dict[str, Any]] = field(default_factory=list)
    path_evidence: list[SearchPathEvidence] = field(default_factory=list)
    candidate_edges: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = StopReason.FRONTIER_EXHAUSTED.value
    failure_reason: str = FailureReason.NONE.value
    llm_route_calls: int = 0
    degraded_to_local: bool = False
    counters: dict[str, int] = field(default_factory=dict)


@dataclass
class RetrievalTrace:
    """供后端和 Unity 只读诊断使用的安全检索轨迹。"""

    retrieval_trace_id: str
    npc_id: str
    target_id: str
    mode: str
    strategy: str
    config_version: int
    policy_summary: dict[str, Any] = field(default_factory=dict)
    direction_source: str = "not_applicable"
    direction: dict[str, Any] = field(default_factory=dict)
    mentions: list[dict[str, Any]] = field(default_factory=list)
    start_node_ids: list[str] = field(default_factory=list)
    target_anchors: list[dict[str, Any]] = field(default_factory=list)
    layer_stats: list[dict[str, Any]] = field(default_factory=list)
    path_evidence: list[dict[str, Any]] = field(default_factory=list)
    selected_edge_ids: list[str] = field(default_factory=list)
    retrieved_node_ids: list[str] = field(default_factory=list)
    vector_query_preview: str = ""
    vector_query_count: int = 0
    vector_hit_usage: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    stop_reason: str = ""
    failure_reason: str = FailureReason.NONE.value
    degraded_to_local: bool = False
    elapsed_sec: float = 0.0


class DirectionProvider(Protocol):
    """方向 provider 的最小实现契约。"""

    def provide(self, request: RetrievalRequest, context: dict[str, Any]) -> DirectionResolution:
        """根据请求和裁剪后的上下文生成方向。"""
