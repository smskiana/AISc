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
    public string planner_version;
    public List<NpcDailyScheduleItem> items = new List<NpcDailyScheduleItem>();
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
