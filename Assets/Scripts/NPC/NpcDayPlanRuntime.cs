using System;
using System.Collections.Generic;

/// <summary>
/// 纯逻辑托管单 NPC 的两段式队列、活动任务、边界和有界变更。
/// </summary>
public sealed class NpcDayPlanRuntime
{
    private static readonly HashSet<string> TerminalReasons = new HashSet<string>(StringComparer.Ordinal)
    {
        "succeeded", "failed", "cancelled", "forced_terminal",
    };

    private static readonly HashSet<string> MutationTypes = new HashSet<string>(StringComparer.Ordinal)
    {
        "append_after_current", "preempt_current", "defer_until_current_terminal", "reject",
    };

    private static readonly HashSet<string> InterruptPolicies = new HashSet<string>(StringComparer.Ordinal)
    {
        "non_interruptible", "player_interruptible", "fully_interruptible",
    };

    private static readonly HashSet<string> CompletionPolicies = new HashSet<string>(StringComparer.Ordinal)
    {
        "duration", "animation_event", "interaction_result", "state_condition", "segment_boundary",
    };

    private readonly List<NpcPlannedTask> _remainingWork = new List<NpcPlannedTask>();
    private readonly List<NpcPlannedTask> _remainingRest = new List<NpcPlannedTask>();
    private readonly Dictionary<string, bool> _mutationResults = new Dictionary<string, bool>(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _mutationReasons = new Dictionary<string, string>(StringComparer.Ordinal);
    private string _acceptedFingerprint = string.Empty;
    private bool _workBoundaryReached;

    public string NpcId { get; private set; } = string.Empty;
    public int GameDay { get; private set; }
    public long PlanRevision { get; private set; }
    public string PlannerVersion { get; private set; } = string.Empty;
    public string ActiveSegmentId { get; private set; } = string.Empty;
    public NpcPlannedTask ActiveTask { get; private set; }
    public bool DayClosed { get; private set; }
    public IReadOnlyList<NpcPlannedTask> RemainingWork => _remainingWork;
    public IReadOnlyList<NpcPlannedTask> RemainingRest => _remainingRest;
    public string LastBoundaryReason { get; private set; } = string.Empty;
    public string LastMutationOperationId { get; private set; } = string.Empty;
    public string LastMutationReason { get; private set; } = string.Empty;
    public string LastTerminalTaskId { get; private set; } = string.Empty;
    public string LastTerminalReason { get; private set; } = string.Empty;
    public string AcceptedFingerprint => _acceptedFingerprint;

    /// <summary>
    /// 原子接收完整日计划；同身份同内容幂等，同 revision 不同内容拒绝。
    /// </summary>
    public bool AcceptPlan(NpcDayPlan plan, out string reason)
    {
        if (!ValidatePlan(plan, out reason))
            return false;

        string fingerprint = BuildFingerprint(plan);
        if (GameDay > 0 && plan.game_day < GameDay)
        {
            reason = "stale_plan_day";
            return false;
        }
        if (plan.game_day == GameDay && plan.plan_revision < PlanRevision)
        {
            reason = "stale_plan_revision";
            return false;
        }
        if (plan.game_day == GameDay && plan.plan_revision == PlanRevision)
        {
            reason = fingerprint == _acceptedFingerprint ? "duplicate_plan_revision" : "revision_content_conflict";
            return fingerprint == _acceptedFingerprint;
        }

        RetireCurrentPlan("replaced_by_new_plan");
        NpcId = plan.npc_id;
        GameDay = plan.game_day;
        PlanRevision = plan.plan_revision;
        PlannerVersion = plan.planner_version ?? string.Empty;
        ActiveSegmentId = "work";
        _remainingWork.AddRange(plan.work_tasks);
        _remainingRest.AddRange(plan.rest_tasks);
        _acceptedFingerprint = fingerprint;
        _mutationResults.Clear();
        _mutationReasons.Clear();
        DayClosed = false;
        _workBoundaryReached = false;
        ActivateNext();
        reason = "plan_accepted";
        return true;
    }

    /// <summary>
    /// 仅消费匹配的活动任务终态，并由模块内部推进队列或阶段。
    /// </summary>
    public bool OnTaskTerminal(string taskId, string terminalReason, out string reason)
    {
        if (ActiveTask == null || !string.Equals(ActiveTask.task_id, taskId, StringComparison.Ordinal))
        {
            reason = "terminal_task_mismatch";
            return false;
        }
        if (!TerminalReasons.Contains(terminalReason))
        {
            reason = "invalid_terminal_reason";
            return false;
        }

        LastTerminalTaskId = ActiveTask.task_id;
        LastTerminalReason = terminalReason;
        ActiveTask = null;
        if (string.Equals(ActiveSegmentId, "work", StringComparison.Ordinal) && _workBoundaryReached)
        {
            ActiveSegmentId = "rest";
            LastBoundaryReason = "rest_segment_started";
        }
        ActivateNext();
        reason = "task_terminal_consumed";
        return true;
    }

    /// <summary>
    /// 裁决工作结束或午夜边界，并返回需要生产适配器执行的稳定结果。
    /// </summary>
    public bool OnSegmentBoundary(string boundaryId, out string reason)
    {
        if (string.Equals(boundaryId, "work_end", StringComparison.Ordinal))
        {
            _workBoundaryReached = true;
            _remainingWork.Clear();
            if (ActiveTask != null && string.Equals(ActiveTask.segment_id, "work", StringComparison.Ordinal))
            {
                LastBoundaryReason = "work_task_continues_after_segment";
                reason = LastBoundaryReason;
                return true;
            }
            ActiveSegmentId = "rest";
            LastBoundaryReason = "rest_segment_started";
            ActivateNext();
            reason = LastBoundaryReason;
            return true;
        }
        if (string.Equals(boundaryId, "day_end", StringComparison.Ordinal))
        {
            _remainingWork.Clear();
            _remainingRest.Clear();
            if (ActiveTask != null)
            {
                LastTerminalTaskId = ActiveTask.task_id;
                LastTerminalReason = "forced_terminal_at_day_boundary";
                ActiveTask = null;
            }
            ActiveSegmentId = string.Empty;
            DayClosed = true;
            LastBoundaryReason = "retired_at_day_end";
            reason = LastBoundaryReason;
            return true;
        }
        reason = "unknown_segment_boundary";
        return false;
    }

    /// <summary>
    /// 应用已由 catalog 解析的单次变更；candidate 请求与解析任务必须保持身份一致。
    /// </summary>
    public bool ApplyMutation(NpcTaskMutation mutation, NpcPlannedTask resolvedTask, out string reason)
    {
        if (mutation == null || string.IsNullOrEmpty(mutation.operation_id))
            return RecordMutation(mutation, "invalid_mutation_operation", false, out reason);
        if (_mutationResults.TryGetValue(mutation.operation_id, out bool previousResult))
        {
            reason = _mutationReasons[mutation.operation_id];
            return previousResult;
        }
        if (!string.Equals(mutation.npc_id, NpcId, StringComparison.Ordinal))
            return RecordMutation(mutation, "mutation_npc_mismatch", false, out reason);
        if (mutation.base_plan_revision != PlanRevision)
            return RecordMutation(mutation, "mutation_revision_conflict", false, out reason);
        if (!MutationTypes.Contains(mutation.mutation_type))
            return RecordMutation(mutation, "unknown_mutation_type", false, out reason);
        if (string.Equals(mutation.mutation_type, "reject", StringComparison.Ordinal))
            return RecordMutation(mutation, "mutation_rejected", true, out reason);
        if (DayClosed)
            return RecordMutation(mutation, "mutation_arrived_after_day_end", false, out reason);
        if (!ValidateResolvedMutationTask(mutation, resolvedTask, out string validationReason))
            return RecordMutation(mutation, validationReason, false, out reason);
        if (!string.Equals(mutation.requested_segment, ActiveSegmentId, StringComparison.Ordinal))
            return RecordMutation(mutation, "mutation_segment_not_active", false, out reason);

        List<NpcPlannedTask> queue = QueueFor(resolvedTask.segment_id);
        if (string.Equals(mutation.mutation_type, "preempt_current", StringComparison.Ordinal))
        {
            if (!CanPreempt(ActiveTask, mutation.source_type))
                return RecordMutation(mutation, "current_task_not_interruptible", false, out reason);
            if (ActiveTask != null)
            {
                LastTerminalTaskId = ActiveTask.task_id;
                LastTerminalReason = string.Equals(mutation.source_type, "player_dialogue", StringComparison.Ordinal)
                    ? "preempted_by_player" : "preempted_by_runtime_decision";
            }
            ActiveSegmentId = resolvedTask.segment_id;
            ActiveTask = resolvedTask;
            PlanRevision++;
            return RecordMutation(mutation, "mutation_preempted_current", true, out reason);
        }

        queue.Insert(0, resolvedTask);
        if (ActiveTask == null && string.Equals(ActiveSegmentId, resolvedTask.segment_id, StringComparison.Ordinal))
            ActivateNext();
        PlanRevision++;
        string acceptedReason = string.Equals(mutation.mutation_type, "append_after_current", StringComparison.Ordinal)
            ? "mutation_appended_after_current" : "mutation_deferred_until_terminal";
        return RecordMutation(mutation, acceptedReason, true, out reason);
    }

    /// <summary>导出不包含 executor、coroutine 或 reservation 的纯状态快照。</summary>
    public NpcDayPlanRuntimeSnapshot CreateSnapshot()
    {
        return new NpcDayPlanRuntimeSnapshot
        {
            npc_id = NpcId,
            game_day = GameDay,
            plan_revision = PlanRevision,
            planner_version = PlannerVersion,
            active_segment_id = ActiveSegmentId,
            active_task = ActiveTask,
            remaining_work_count = _remainingWork.Count,
            remaining_rest_count = _remainingRest.Count,
            last_boundary_reason = LastBoundaryReason,
            last_mutation_operation_id = LastMutationOperationId,
            last_mutation_reason = LastMutationReason,
            last_terminal_task_id = LastTerminalTaskId,
            last_terminal_reason = LastTerminalReason,
            day_closed = DayClosed,
        };
    }

    /// <summary>导出可持久化的稳定计划；活动任务放回对应队首，读档后由 executor 重建。</summary>
    public NpcDayPlan ExportPlan(string operationId)
    {
        var work = new List<NpcPlannedTask>(_remainingWork);
        var rest = new List<NpcPlannedTask>(_remainingRest);
        if (ActiveTask != null)
        {
            if (string.Equals(ActiveTask.segment_id, "work", StringComparison.Ordinal)) work.Insert(0, ActiveTask);
            else rest.Insert(0, ActiveTask);
        }
        return new NpcDayPlan
        {
            operation_id = operationId ?? string.Empty,
            npc_id = NpcId,
            game_day = GameDay,
            plan_revision = PlanRevision,
            planner_version = PlannerVersion,
            segments = new List<NpcPlanSegmentDefinition>
            {
                new NpcPlanSegmentDefinition { segment_id = "work", starts_at = "08:00", ends_at = "17:00", boundary_policy = "active_task_continues" },
                new NpcPlanSegmentDefinition { segment_id = "rest", starts_at = "17:00", ends_at = "24:00", boundary_policy = "force_terminal_at_day_end" },
            },
            work_tasks = work,
            rest_tasks = rest,
        };
    }

    private static bool ValidatePlan(NpcDayPlan plan, out string reason)
    {
        if (plan == null || string.IsNullOrEmpty(plan.npc_id) || plan.game_day < 1 || plan.plan_revision < 1)
        {
            reason = "invalid_plan_envelope";
            return false;
        }
        if (!HasRequiredSegments(plan.segments))
        {
            reason = "invalid_segment_definitions";
            return false;
        }
        var taskIds = new HashSet<string>(StringComparer.Ordinal);
        if (!ValidateTasks(plan.work_tasks, "work", taskIds, out reason))
            return false;
        return ValidateTasks(plan.rest_tasks, "rest", taskIds, out reason);
    }

    private static bool HasRequiredSegments(List<NpcPlanSegmentDefinition> segments)
    {
        if (segments == null)
            return false;
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (NpcPlanSegmentDefinition segment in segments)
        {
            if (segment != null && !string.IsNullOrEmpty(segment.segment_id)
                && !string.IsNullOrEmpty(segment.starts_at) && !string.IsNullOrEmpty(segment.ends_at)
                && !string.IsNullOrEmpty(segment.boundary_policy))
                ids.Add(segment.segment_id);
        }
        return ids.SetEquals(new[] { "work", "rest" });
    }

    private static bool ValidateTasks(List<NpcPlannedTask> tasks, string segmentId, HashSet<string> taskIds, out string reason)
    {
        if (tasks == null)
        {
            reason = "missing_segment_queue";
            return false;
        }
        foreach (NpcPlannedTask task in tasks)
        {
            if (task == null || string.IsNullOrEmpty(task.task_id) || string.IsNullOrEmpty(task.candidate_id)
                || string.IsNullOrEmpty(task.action_id) || string.IsNullOrEmpty(task.location_id))
            {
                reason = "invalid_planned_task";
                return false;
            }
            if (!taskIds.Add(task.task_id))
            {
                reason = "duplicate_task_id";
                return false;
            }
            if (!string.Equals(task.segment_id, segmentId, StringComparison.Ordinal))
            {
                reason = "task_segment_mismatch";
                return false;
            }
            if (task.lifecycle_action)
            {
                reason = "lifecycle_action_not_queueable";
                return false;
            }
            if (!InterruptPolicies.Contains(task.interrupt_policy))
            {
                reason = "invalid_interrupt_policy";
                return false;
            }
            if (!CompletionPolicies.Contains(task.completion_policy_id))
            {
                reason = "invalid_completion_policy_id";
                return false;
            }
            if (string.Equals(task.completion_policy_id, "duration", StringComparison.Ordinal)
                && task.duration_gameplay_seconds <= 0)
            {
                reason = "invalid_duration_gameplay_seconds";
                return false;
            }
        }
        reason = string.Empty;
        return true;
    }

    private static bool ValidateResolvedMutationTask(NpcTaskMutation mutation, NpcPlannedTask task, out string reason)
    {
        if (task == null || !string.Equals(task.candidate_id, mutation.candidate_id, StringComparison.Ordinal))
        {
            reason = "mutation_candidate_mismatch";
            return false;
        }
        if (!string.Equals(task.segment_id, mutation.requested_segment, StringComparison.Ordinal))
        {
            reason = "mutation_segment_mismatch";
            return false;
        }
        var taskIds = new HashSet<string>(StringComparer.Ordinal);
        return ValidateTasks(new List<NpcPlannedTask> { task }, mutation.requested_segment, taskIds, out reason);
    }

    private static bool CanPreempt(NpcPlannedTask activeTask, string sourceType)
    {
        if (activeTask == null)
            return true;
        if (string.Equals(activeTask.interrupt_policy, "fully_interruptible", StringComparison.Ordinal))
            return true;
        return string.Equals(activeTask.interrupt_policy, "player_interruptible", StringComparison.Ordinal)
            && string.Equals(sourceType, "player_dialogue", StringComparison.Ordinal);
    }

    private List<NpcPlannedTask> QueueFor(string segmentId)
    {
        return string.Equals(segmentId, "work", StringComparison.Ordinal) ? _remainingWork : _remainingRest;
    }

    private void ActivateNext()
    {
        if (DayClosed || ActiveTask != null)
            return;
        List<NpcPlannedTask> queue = QueueFor(ActiveSegmentId);
        if (queue.Count == 0)
            return;
        ActiveTask = queue[0];
        queue.RemoveAt(0);
    }

    private void RetireCurrentPlan(string reason)
    {
        _remainingWork.Clear();
        _remainingRest.Clear();
        if (ActiveTask != null)
        {
            LastTerminalTaskId = ActiveTask.task_id;
            LastTerminalReason = reason;
        }
        ActiveTask = null;
    }

    private bool RecordMutation(NpcTaskMutation mutation, string reason, bool accepted, out string outputReason)
    {
        LastMutationOperationId = mutation?.operation_id ?? string.Empty;
        LastMutationReason = reason;
        if (mutation != null && !string.IsNullOrEmpty(mutation.operation_id))
        {
            _mutationResults[mutation.operation_id] = accepted;
            _mutationReasons[mutation.operation_id] = reason;
        }
        outputReason = reason;
        return accepted;
    }

    private static string BuildFingerprint(NpcDayPlan plan)
    {
        var parts = new List<string> { plan.npc_id, plan.game_day.ToString(), plan.plan_revision.ToString(), plan.planner_version ?? string.Empty };
        foreach (NpcPlanSegmentDefinition segment in plan.segments)
            parts.Add($"{segment.segment_id}:{segment.starts_at}:{segment.ends_at}:{segment.boundary_policy}");
        AppendFingerprint(parts, plan.work_tasks);
        AppendFingerprint(parts, plan.rest_tasks);
        return string.Join("|", parts);
    }

    private static void AppendFingerprint(List<string> parts, List<NpcPlannedTask> tasks)
    {
        foreach (NpcPlannedTask task in tasks)
            parts.Add($"{task.task_id}:{task.candidate_id}:{task.action_id}:{task.location_id}:{task.segment_id}:{task.completion_policy_id}:{task.interrupt_policy}:{task.duration_gameplay_seconds}");
    }
}
