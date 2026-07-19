using System;
using System.Collections.Generic;

/// <summary>
/// 表示一次协议 envelope 的轻量诊断轨迹。
/// </summary>
[Serializable]
public sealed class ProtocolTraceEntry
{
    public string direction;
    public string type;
    public string request_id;
    public string session_id;
    public long sequence;
    public string sent_at;
    public string observed_at;
    public string error_code;
}

/// <summary>
/// 表示 NPC 正式任务的只读诊断快照。
/// </summary>
[Serializable]
public sealed class NpcTaskDiagnosticSnapshot
{
    public string npc_id;
    public string request_id;
    public string action_id;
    public string target_location_id;
    public string actual_location_id;
    public string phase;
    public int progress_revision;
    public bool motion_locked;
    public bool is_terminal;
}

/// <summary>
/// 表示 Unity 权威 NPC-NPC 社交 session 的阶段与稳定终态原因。
/// </summary>
[Serializable]
public sealed class NpcSocialDiagnosticSnapshot
{
    public string request_id;
    public string candidate_id;
    public string npc_id;
    public string target_npc_id;
    public string location_id;
    public string phase;
    public string terminal_reason;
    public bool is_terminal;
    public long world_revision;
}

/// <summary>
/// 表示一次隔离 NPC 社交协议探针的机器可读裁决。
/// </summary>
[Serializable]
public sealed class NpcSocialProbeResult
{
    public bool success;
    public string scenario;
    public string request_id;
    public string write_scope = "isolated_in_memory_only";
    public bool both_reserved_initially;
    public bool both_released;
    public bool content_accepted;
    public bool late_content_accepted;
    public string terminal_phase;
    public string terminal_reason;
    public string failure_reason;
}

/// <summary>
/// 表示后端某一轮对话记忆检索的只读诊断快照。
/// </summary>
[Serializable]
public class ConversationRetrievalDiagnosticSnapshot
{
    public string npc_id;
    public string conversation_id;
    public string mode;
    public string speaker_id;
    public List<string> participant_ids = new();
    public string current_utterance;
    public List<string> recent_dialogue_preview = new();
    public List<string> participant_impressions = new();
    public List<string> start_node_ids = new();
    public List<string> selected_edge_ids = new();
    public List<string> retrieved_node_ids = new();
    public string vector_query_preview;
    public bool vector_fallback_used;
    public int working_memory_turn_count;
    public string rolling_summary_preview;
    public string persistence_status;
    public string failure_reason;
    public string retrieval_trace_id;
    public string strategy;
    public string direction_source;
    public RetrievalDirectionDiagnostic direction;
    public List<RetrievalMentionDiagnostic> mentions = new();
    public List<RetrievalAnchorDiagnostic> target_anchors = new();
    public List<RetrievalLayerDiagnostic> layer_stats = new();
    public List<RetrievalPathDiagnostic> path_evidence = new();
    public int vector_query_count;
    public List<RetrievalVectorUsageDiagnostic> vector_hit_usage = new();
    public string stop_reason;
    public bool degraded_to_local;
    public RetrievalPolicyDiagnostic policy_summary;
    public string original_query_preview;
    public int original_query_chars;
    public string retrieval_query_preview;
    public int retrieval_query_chars;
    public string retrieval_query_source;
    public List<string> query_constraints = new();
    public string selected_recent_turn_preview;
    public int selected_recent_turn_chars;
    public string selection_reason;
    public string embedding_query_preview;
    public int embedding_query_chars;
    public List<string> direction_validation_errors = new();
    public List<string> direction_calibrations = new();
    public string query_fallback_reason;
    public List<string> graph_candidate_ids = new();
    public List<RetrievalFinalEntryDiagnostic> final_entries = new();
    public List<RetrievalEvictedEntryDiagnostic> evicted_entries = new();
    public int final_entry_count;
    public int final_context_chars;
}

/// <summary>
/// 表示一次通用记忆检索快照，供玩家、NPC 和夜间模式共用。
/// </summary>
[Serializable]
public sealed class MemoryRetrievalDiagnosticSnapshot : ConversationRetrievalDiagnosticSnapshot
{
}

/// <summary>
/// 表示通用记忆检索快照接口的响应包装。
/// </summary>
[Serializable]
public sealed class MemoryRetrievalDiagnosticResponse
{
    public int count;
    public List<MemoryRetrievalDiagnosticSnapshot> items = new();
}

/// <summary>
/// 表示后端当前或最近一次午夜维护的结构化快照。
/// </summary>
[Serializable]
public sealed class MidnightMaintenanceDiagnosticSnapshot
{
    public string operation_id;
    public string status;
    public string phase;
    public int target_count;
    public string direction_source;
    public int llm_direction_calls;
    public Dictionary<string, string> retrieval_trace_ids = new();
    public int impression_planned_count;
    public int impression_success_count;
    public int impression_fallback_count;
    public List<string> impression_failed_owner_ids = new();
    public int extraction_event_owner_count;
    public int extraction_success_count;
    public int extraction_failure_count;
    public int extraction_invalid_node_count;
    public int extraction_invalid_edge_count;
    public List<string> extraction_failed_owner_ids = new();
    public List<string> failure_reasons = new();
    public Dictionary<string, float> stage_elapsed_sec = new();
    public float parallel_wall_sec;
    public float total_elapsed_sec;
}

/// <summary>
/// 表示一次玩家快捷回复生成的有界安全摘要。
/// </summary>
[Serializable]
public sealed class PlayerReplySuggestionDiagnosticSnapshot
{
    public string reply_trace_id;
    public string npc_id;
    public string player_id;
    public string task_id;
    public string speaker_role_expected;
    public string recipient_role_expected;
    public List<string> context_keys = new();
    public int choice_count;
    public List<string> choice_previews = new();
    public List<string> rejected_choice_previews = new();
    public List<string> rejection_reasons = new();
    public bool fallback_used;
    public string failure_reason;
    public int elapsed_ms;
}

/// <summary>
/// 表示玩家快捷回复安全摘要接口的响应包装。
/// </summary>
[Serializable]
public sealed class PlayerReplySuggestionDiagnosticResponse
{
    public int count;
    public List<PlayerReplySuggestionDiagnosticSnapshot> items = new();
}

/// <summary>
/// 表示只读记忆检索探针的最小控制结果。
/// </summary>
[Serializable]
public sealed class MemoryRetrievalProbeResult
{
    public bool success;
    public string retrieval_trace_id;
    public string failure_reason;
}

/// <summary>
/// 表示后端方向契约的安全诊断字段。
/// </summary>
[Serializable]
public sealed class RetrievalDirectionDiagnostic
{
    public List<string> entity_mentions = new();
    public List<string> location_mentions = new();
    public List<string> themes = new();
    public List<string> relation_facets = new();
    public string time_scope;
    public string recall_intent;
    public List<string> negative_directions = new();
    public string retrieval_query;
    public List<string> query_constraints = new();
}

/// <summary>
/// 表示一个自然语言 mention 的稳定解析结果。
/// </summary>
[Serializable]
public sealed class RetrievalMentionDiagnostic
{
    public string text;
    public string entity_id;
    public string entity_type;
    public string source;
    public float confidence;
}

/// <summary>
/// 表示不进入初始前沿的目标锚点。
/// </summary>
[Serializable]
public sealed class RetrievalAnchorDiagnostic
{
    public string node_id;
    public string usage;
}

/// <summary>
/// 表示单层深搜的规模统计。
/// </summary>
[Serializable]
public sealed class RetrievalLayerDiagnostic
{
    public int depth;
    public int frontier_nodes;
    public int neighbor_edges;
    public int beam_nodes;
    public int candidate_edges;
}

/// <summary>
/// 表示实际采用路径的安全证据。
/// </summary>
[Serializable]
public sealed class RetrievalPathDiagnostic
{
    public string node_id;
    public string edge_id;
    public float score;
    public string from_node_id;
}

/// <summary>
/// 表示向量命中的用途，不暴露节点正文。
/// </summary>
[Serializable]
public sealed class RetrievalVectorUsageDiagnostic
{
    public string node_id;
    public int rank;
    public float similarity;
    public string usage;
}

/// <summary>
/// 表示实际进入对白 Prompt 的完整原子记忆条目。
/// </summary>
[Serializable]
public sealed class RetrievalFinalEntryDiagnostic
{
    public string node_id;
    public string type;
    public float score;
    public List<RetrievalScoreComponentDiagnostic> score_components = new();
    public int rendered_chars;
}

/// <summary>
/// 表示最终评分中的一个可观测分量。
/// </summary>
[Serializable]
public sealed class RetrievalScoreComponentDiagnostic
{
    public string name;
    public float value;
}

/// <summary>
/// 表示最终上下文预算淘汰的完整记忆条目。
/// </summary>
[Serializable]
public sealed class RetrievalEvictedEntryDiagnostic
{
    public string node_id;
    public string reason;
}

/// <summary>
/// 表示本轮生效的简短策略摘要。
/// </summary>
[Serializable]
public sealed class RetrievalPolicyDiagnostic
{
    public string strategy;
    public int final_memory_limit;
    public int max_direction_context_chars;
    public int final_context_max_chars;
    public int max_depth;
    public int beam_width;
    public int max_neighbors_per_node;
    public int max_expanded_edges;
}

/// <summary>
/// 表示后端冷启动初始知识投影诊断响应。
/// </summary>
[Serializable]
public sealed class InitialKnowledgeProjectionDiagnosticSnapshot
{
    public string npc_id;
    public int count;
    public List<InitialKnowledgeProjectionDiagnosticItem> items = new();
    public string failure_reason;
}

/// <summary>
/// 表示单条初始知识投影的权限、来源和实际图连接。
/// </summary>
[Serializable]
public sealed class InitialKnowledgeProjectionDiagnosticItem
{
    public string observer_id;
    public string fact_id;
    public string status;
    public string projection_id;
    public string node_id;
    public string value_preview;
    public string knowledge_scope;
    public string visibility_rule;
    public string visibility_reason;
    public string source_type;
    public float confidence;
    public float importance;
    public List<string> subject_ids = new();
    public List<string> location_ids = new();
    public int created_day;
    public List<string> edge_ids = new();
    public List<string> person_node_ids = new();
    public string failure_reason;
}

/// <summary>
/// 表示运行中的 Unity 游戏状态摘要。
/// </summary>
[Serializable]
public sealed class RuntimeDiagnosticSnapshot
{
    public bool is_playing;
    public string scene;
    public bool game_manager_present;
    public bool gameplay_ready;
    public bool is_sleeping;
    public bool is_dialogue_active;
    public string dialogue_npc_id;
    public string player_location_id;
    public GameTime game_time;
    public PauseDiagnosticSnapshot pause;
    public ConnectionDiagnosticSnapshot connection;
    public SaveDiagnosticSnapshot save;
    public WorldPreparationDiagnosticSnapshot world_preparation;
    public int npc_state_count;
    public int npc_entity_count;
    public List<NpcTaskDiagnosticSnapshot> npc_tasks = new();
    public List<NpcRuntimeStateDiagnosticSnapshot> npc_runtime_states = new();
    public List<ConversationRetrievalDiagnosticSnapshot> active_conversations = new();
}

/// <summary>
/// 表示 Unity 已接收的世界准备阶段，不携带 UI 文案或 LLM 原文。
/// </summary>
[Serializable]
public sealed class WorldPreparationDiagnosticSnapshot
{
    public string operation_id;
    public string flow;
    public string phase;
    public bool is_active;
    public float progress_floor;
    public string failure_reason;
    public int target_game_day;
}

/// <summary>
/// 表示当前暂停状态及其所有来源。
/// </summary>
[Serializable]
public sealed class PauseDiagnosticSnapshot
{
    public bool is_paused;
    public string[] active_sources = Array.Empty<string>();
    public bool gameplay_paused;
    public bool ui_paused;
    public bool fx_paused;
    public string[] gameplay_sources = Array.Empty<string>();
    public string[] ui_sources = Array.Empty<string>();
    public string[] fx_sources = Array.Empty<string>();
    public float unity_time_scale;
    public int registered_fx_count;
    public int domain_paused_fx_count;
}

/// <summary>
/// 表示 WebSocket 和协议协商状态。
/// </summary>
[Serializable]
public sealed class ConnectionDiagnosticSnapshot
{
    public bool is_connected;
    public bool is_connecting;
    public bool connect_attempt_finished;
    public bool protocol_negotiated;
    public string session_id;
    public string connection_error;
    public string protocol_error;
}

/// <summary>
/// 表示 Unity 存档事务当前阶段。
/// </summary>
[Serializable]
public sealed class SaveDiagnosticSnapshot
{
    public string phase;
    public string checkpoint_id;
    public bool is_purging_for_new_game;
    public string last_new_game_purge_error;
}

/// <summary>
/// 表示一个机器可读的健康问题。
/// </summary>
[Serializable]
public sealed class DiagnosticIssue
{
    public string code;
    public string severity;
    public string message;
}

/// <summary>
/// 表示 Unity 业务系统总体健康状态。
/// </summary>
[Serializable]
public sealed class DiagnosticHealthReport
{
    public string status;
    public List<DiagnosticIssue> issues = new();
    public RuntimeDiagnosticSnapshot snapshot;
}
