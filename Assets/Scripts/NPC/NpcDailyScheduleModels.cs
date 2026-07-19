using System;
using System.Collections.Generic;

/// <summary>
/// 保存 Unity 权威剩余计划中的稳定跨端字段。
/// </summary>
[Serializable]
public sealed class NpcDailyScheduleItem
{
    public string candidate_id;
    public string action_id;
    public string location_id;
    public string target_person_id;
    public string planned_start_time;
    public int execution_window_before_minutes = 30;
    public int execution_window_after_minutes = 30;
    public string necessity;
    public string primary_group;
    public List<string> groups = new List<string>();
    public List<string> evidence_ids = new List<string>();
    public string source;
    public string miss_policy;
}

/// <summary>定义日计划中可扩展的阶段边界。</summary>
[Serializable]
public sealed class NpcPlanSegmentDefinition
{
    public string segment_id;
    public string starts_at;
    public string ends_at;
    public string boundary_policy;
}

/// <summary>保存不含精确执行时间的两段式计划任务。</summary>
[Serializable]
public sealed class NpcPlannedTask
{
    public string task_id;
    public string candidate_id;
    public string action_id;
    public string location_id;
    public string target_person_id;
    public string segment_id;
    public string completion_policy_id;
    public string interrupt_policy;
    public int duration_gameplay_seconds;
    public bool lifecycle_action;
    public string source;
    public List<string> evidence_ids = new List<string>();
}

/// <summary>表示单 NPC、单游戏日的完整两段式计划。</summary>
[Serializable]
public sealed class NpcDayPlan
{
    public string operation_id;
    public string npc_id;
    public int game_day;
    public long plan_revision;
    public string planner_version;
    public List<NpcPlanSegmentDefinition> segments = new List<NpcPlanSegmentDefinition>();
    public List<NpcPlannedTask> work_tasks = new List<NpcPlannedTask>();
    public List<NpcPlannedTask> rest_tasks = new List<NpcPlannedTask>();
}

/// <summary>描述玩家对话或未来决策产生的一次有界任务变更。</summary>
[Serializable]
public sealed class NpcTaskMutation
{
    public string operation_id;
    public string npc_id;
    public long base_plan_revision;
    public string source_type;
    public string mutation_type;
    public string candidate_id;
    public string requested_segment;
    public string reason;
}

/// <summary>导出纯运行时的队列、边界、变更和最近终态。</summary>
[Serializable]
public sealed class NpcDayPlanRuntimeSnapshot
{
    public string npc_id;
    public int game_day;
    public long plan_revision;
    public string planner_version;
    public string active_segment_id;
    public NpcPlannedTask active_task;
    public int remaining_work_count;
    public int remaining_rest_count;
    public string last_boundary_reason;
    public string last_mutation_operation_id;
    public string last_mutation_reason;
    public string last_terminal_task_id;
    public string last_terminal_reason;
    public bool day_closed;
}

/// <summary>
/// 表示后端一次整体提交的单 NPC 日计划。
/// </summary>
[Serializable]
public sealed class NpcDailyScheduleReadyMsg
{
    public string type;
    public string operation_id;
    public string npc_id;
    public int game_day;
    public long schedule_revision;
    public long plan_revision;
    public string planner_version;
    public string status;
    public string failure_reason;
    public List<NpcDailyScheduleItem> items = new List<NpcDailyScheduleItem>();
    public List<NpcPlanSegmentDefinition> segments = new List<NpcPlanSegmentDefinition>();
    public List<NpcPlannedTask> work_tasks = new List<NpcPlannedTask>();
    public List<NpcPlannedTask> rest_tasks = new List<NpcPlannedTask>();
}

/// <summary>引用后端已经确认接收的 Unity 冻结日程世界快照。</summary>
[Serializable]
public sealed class NpcScheduleSnapshotReference
{
    public string snapshot_id;
    public long time_revision;
    public long world_revision;
    public int game_day;
}

/// <summary>保存一条有界 Unity 日程重规划 pending。</summary>
[Serializable]
public sealed class NpcScheduleReplanPending
{
    public string operation_id;
    public string npc_id;
    public int game_day;
    public long base_schedule_revision;
    public string snapshot_id;
    public long time_revision;
    public long world_revision;
    public GameTime requested_game_time;
    public float started_realtime;
    public string status;
}

/// <summary>保存最近一次重规划本地终态。</summary>
[Serializable]
public sealed class NpcScheduleReplanTerminal
{
    public string operation_id;
    public int game_day;
    public long base_schedule_revision;
    public string reason;
}

/// <summary>
/// 仅暴露日程裁决与剩余项的只读诊断，不包含 LLM 原文或临时请求。
/// </summary>
[Serializable]
public sealed class NpcDailyScheduleDiagnosticSnapshot
{
    public string npc_id;
    public int schedule_day;
    public long schedule_revision;
    public string planner_version;
    public int remaining_count;
    public string pending_candidate_id;
    public string last_decision_reason;
    public string payload_fingerprint;
    public string last_operation_id;
    public bool evening_compressed;
    public int compression_before_count;
    public int compression_after_count;
    public string last_replan_operation_id;
    public string last_replan_status;
    public ScheduleOwnerDiagnosticSnapshot backend_owner_trace;
}

/// <summary>
/// 表示后端单 owner 规划、证据、校验与 fallback 的安全 trace。
/// </summary>
[Serializable]
public sealed class ScheduleOwnerDiagnosticSnapshot
{
    public string operation_id;
    public string npc_id;
    public int game_day;
    public string status;
    public int candidate_count;
    public int selected_count;
    public string fallback_seed;
    public float elapsed_sec;
    public string failure_reason;
    public string failure_detail;
    public bool provider_call_not_cancelled;
    public Dictionary<string, int> rejection_counts = new();
    public Dictionary<string, int> memory_stats = new();
    public Dictionary<string, string> fallback_reasons = new();
    public Dictionary<string, int> candidate_group_counts = new();
    public List<string> evidence_ids = new();
    public string validation_status;
    public string execution_phase;
}

/// <summary>
/// 包装后端 owner trace 列表，避免 Unity 解析后端内部对象。
/// </summary>
[Serializable]
public sealed class ScheduleOwnerDiagnosticResponse
{
    public int count;
    public List<ScheduleOwnerDiagnosticSnapshot> items = new();
}

/// <summary>
/// 聚合互动或运行时恢复重规划的 Unity 托管状态与后端 owner trace。
/// </summary>
[Serializable]
public sealed class InteractionReplanDiagnosticSnapshot
{
    public string npc_id;
    public string operation_id;
    public string unity_status;
    public long schedule_revision;
    public string pending_candidate_id;
    public ScheduleOwnerDiagnosticSnapshot backend_owner_trace;
    public string failure_reason;
}

/// <summary>
/// 返回白名单日程探针的隔离写入范围和稳定裁决。
/// </summary>
[Serializable]
public sealed class DailyScheduleProbeResult
{
    public bool success;
    public string scenario;
    public string write_scope = "isolated_in_memory_only";
    public string decision;
    public string reason;
    public int remaining_count;
    public string failure_reason;
    public string status;
    public int item_count;
    public string operation_id;
    public ScheduleOwnerDiagnosticSnapshot trace;
}

public enum NpcScheduleSwitchDecision
{
    Switch,
    Defer,
    SkipNext,
    RequestReplan,
}

/// <summary>
/// 返回切换决定和可诊断的稳定原因。
/// </summary>
public readonly struct NpcScheduleSwitchResult
{
    public readonly NpcScheduleSwitchDecision Decision;
    public readonly string Reason;

    public NpcScheduleSwitchResult(NpcScheduleSwitchDecision decision, string reason)
    {
        Decision = decision;
        Reason = reason;
    }
}

/// <summary>
/// 隔离特殊锁定状态，允许后续注册新裁决而不修改执行器。
/// </summary>
public interface INpcScheduleSwitchPolicy
{
    NpcScheduleSwitchResult Evaluate(bool hasSocialDialogueLock, bool windowExpired, string missPolicy);
}

/// <summary>
/// 实现默认可切换、社交对话延迟与窗口失效策略。
/// </summary>
public sealed class DefaultNpcScheduleSwitchPolicy : INpcScheduleSwitchPolicy
{
    public NpcScheduleSwitchResult Evaluate(bool hasSocialDialogueLock, bool windowExpired, string missPolicy)
    {
        if (hasSocialDialogueLock && !windowExpired)
            return new NpcScheduleSwitchResult(NpcScheduleSwitchDecision.Defer, "npc_social_dialogue_locked");
        if (!windowExpired)
            return new NpcScheduleSwitchResult(NpcScheduleSwitchDecision.Switch, "schedule_window_active");
        return string.Equals(missPolicy, "request_replan", StringComparison.Ordinal)
            ? new NpcScheduleSwitchResult(NpcScheduleSwitchDecision.RequestReplan, "schedule_window_expired")
            : new NpcScheduleSwitchResult(NpcScheduleSwitchDecision.SkipNext, "schedule_window_expired");
    }
}
