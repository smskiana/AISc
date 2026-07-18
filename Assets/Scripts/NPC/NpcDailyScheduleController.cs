using System;
using System.Collections.Generic;

/// <summary>
/// 托管单 NPC 剩余计划、revision 幂等和本地 pending 裁决。
/// </summary>
public sealed class NpcDailyScheduleController
{
    private readonly INpcScheduleSwitchPolicy _switchPolicy;
    private readonly List<NpcDailyScheduleItem> _remaining = new List<NpcDailyScheduleItem>();
    private string _acceptedPayloadFingerprint = string.Empty;

    public int ScheduleDay { get; private set; }
    public long ScheduleRevision { get; private set; }
    public string PlannerVersion { get; private set; } = string.Empty;
    public NpcDailyScheduleItem PendingCandidate { get; private set; }
    public IReadOnlyList<NpcDailyScheduleItem> Remaining => _remaining;
    public string LastDecisionReason { get; private set; } = string.Empty;
    public string AcceptedPayloadFingerprint => _acceptedPayloadFingerprint;
    public string LastOperationId { get; private set; } = string.Empty;

    public NpcDailyScheduleController(INpcScheduleSwitchPolicy switchPolicy = null)
    {
        _switchPolicy = switchPolicy ?? new DefaultNpcScheduleSwitchPolicy();
    }

    /// <summary>
    /// 幂等接收完整计划；同 revision 不同内容会被拒绝。
    /// </summary>
    public bool TryReplace(NpcDailyScheduleReadyMsg message, out string reason)
    {
        if (message == null || message.game_day < 1 || message.schedule_revision < 1)
        {
            reason = "invalid_schedule_envelope";
            return false;
        }
        if (message.status == "failed" || message.status == "skipped")
        {
            reason = "non_authoritative_schedule_status";
            return false;
        }
        if (ScheduleDay > 0 && message.game_day < ScheduleDay)
        {
            reason = "stale_schedule_day";
            return false;
        }
        string fingerprint = BuildFingerprint(message.items);
        if (message.schedule_revision < ScheduleRevision)
        {
            reason = "stale_schedule_revision";
            return false;
        }
        if (message.schedule_revision == ScheduleRevision)
        {
            reason = fingerprint == _acceptedPayloadFingerprint ? "duplicate_schedule_revision" : "revision_content_conflict";
            return fingerprint == _acceptedPayloadFingerprint;
        }
        _remaining.Clear();
        _remaining.AddRange(message.items ?? new List<NpcDailyScheduleItem>());
        ScheduleDay = message.game_day;
        ScheduleRevision = message.schedule_revision;
        PlannerVersion = message.planner_version ?? string.Empty;
        LastOperationId = message.operation_id ?? string.Empty;
        PendingCandidate = null;
        _acceptedPayloadFingerprint = fingerprint;
        reason = "schedule_replaced";
        return true;
    }

    /// <summary>
    /// 按 Unity 当前分钟评估下一候选，不把到点等同于完成。
    /// </summary>
    public NpcScheduleSwitchResult EvaluateNext(int hour, int minute, bool hasSocialDialogueLock)
    {
        if (_remaining.Count == 0)
            return Record(new NpcScheduleSwitchResult(NpcScheduleSwitchDecision.SkipNext, "schedule_empty"));
        PendingCandidate = _remaining[0];
        if (!TryMinute(PendingCandidate.planned_start_time, out int planned))
            return Record(new NpcScheduleSwitchResult(NpcScheduleSwitchDecision.SkipNext, "invalid_planned_start_time"));
        int now = hour * 60 + minute;
        bool expired = now > planned + PendingCandidate.execution_window_after_minutes;
        if (now < planned - PendingCandidate.execution_window_before_minutes)
            return Record(new NpcScheduleSwitchResult(NpcScheduleSwitchDecision.Defer, "schedule_window_not_started"));
        return Record(_switchPolicy.Evaluate(hasSocialDialogueLock, expired, PendingCandidate.miss_policy));
    }

    /// <summary>
    /// 仅在真实任务终态或明确 skip 后消费候选。
    /// </summary>
    public bool Consume(string candidateId)
    {
        if (_remaining.Count == 0 || !string.Equals(_remaining[0].candidate_id, candidateId, StringComparison.Ordinal))
            return false;
        _remaining.RemoveAt(0);
        PendingCandidate = null;
        return true;
    }

    /// <summary>
    /// 导出可进入 Unity 主存档的剩余计划；pending 与 in-flight 均为运行态，不随存档保留。
    /// </summary>
    public List<NpcDailyScheduleItem> ExportRemaining()
    {
        return new List<NpcDailyScheduleItem>(_remaining);
    }

    /// <summary>
    /// 从 Unity 主存档恢复同日剩余计划，并故意清除临时等待状态。
    /// </summary>
    public void Restore(int scheduleDay, long scheduleRevision, string plannerVersion, List<NpcDailyScheduleItem> remaining)
    {
        ScheduleDay = scheduleDay;
        ScheduleRevision = scheduleRevision;
        PlannerVersion = plannerVersion ?? string.Empty;
        PendingCandidate = null;
        _remaining.Clear();
        _remaining.AddRange(remaining ?? new List<NpcDailyScheduleItem>());
        _acceptedPayloadFingerprint = BuildFingerprint(_remaining);
        LastOperationId = string.Empty;
        LastDecisionReason = "schedule_restored";
    }

    /// <summary>
    /// 跨日时丢弃旧日剩余计划，防止旧候选在次日恢复。
    /// </summary>
    public void ClearForNewDay()
    {
        _remaining.Clear();
        PendingCandidate = null;
        LastDecisionReason = "schedule_day_expired";
    }

    private NpcScheduleSwitchResult Record(NpcScheduleSwitchResult result)
    {
        LastDecisionReason = result.Reason;
        return result;
    }

    private static bool TryMinute(string value, out int minute)
    {
        minute = 0;
        if (string.IsNullOrEmpty(value) || value.Length != 5 || value[2] != ':')
            return false;
        if (!int.TryParse(value.Substring(0, 2), out int hour) || !int.TryParse(value.Substring(3, 2), out int part))
            return false;
        if (hour < 0 || hour > 23 || part < 0 || part > 59)
            return false;
        minute = hour * 60 + part;
        return true;
    }

    private static string BuildFingerprint(List<NpcDailyScheduleItem> items)
    {
        if (items == null)
            return string.Empty;
        return string.Join("|", items.ConvertAll(item => $"{item.candidate_id}:{item.action_id}:{item.location_id}:{item.planned_start_time}"));
    }
}
