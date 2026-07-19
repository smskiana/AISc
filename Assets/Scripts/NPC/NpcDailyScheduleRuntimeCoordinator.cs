using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 将两段式日计划协议和 Unity 生命周期适配到纯逻辑 runtime 与唯一任务执行器。
/// </summary>
public sealed class NpcDailyScheduleRuntimeCoordinator
{
    private readonly Dictionary<string, NpcDayPlanRuntime> _plans = new Dictionary<string, NpcDayPlanRuntime>(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _taskByRequest = new Dictionary<string, string>(StringComparer.Ordinal);
    private readonly Func<string, NpcEntity> _getNpc;
    private readonly NpcBehaviorApplier _behaviorApplier;
    private readonly NpcAmbientBehaviorController _ambient;
    private readonly NpcSocialCandidateController _social;
    private int _lastBoundaryDay;
    private bool _workBoundarySent;
    private bool _dayBoundarySent;

    // 兼容旧只读 API；分钟 controller 已不再拥有生产任务。
    public IReadOnlyDictionary<string, NpcDailyScheduleController> Schedules { get; } = new Dictionary<string, NpcDailyScheduleController>();

    public NpcDailyScheduleRuntimeCoordinator(Func<string, NpcEntity> getNpc, NpcBehaviorApplier behaviorApplier,
        NpcAmbientBehaviorController ambient, NpcSocialCandidateController social, NpcActionResultReporter reporter,
        NpcScheduleReplanTracker replans = null)
    {
        _getNpc = getNpc;
        _behaviorApplier = behaviorApplier;
        _ambient = ambient;
        _social = social;
        if (reporter != null) reporter.TerminalReported += HandleTaskTerminal;
    }

    /// <summary>原子接收 V2 双段计划；失败结果和旧 V1 消息不得接管 owner。</summary>
    public void Receive(NpcDailyScheduleReadyMsg message)
    {
        if (message == null || string.IsNullOrWhiteSpace(message.npc_id)) return;
        if (message.type != "NPC_DAY_PLAN_READY" || message.status == "failed" || message.status == "skipped") return;
        var plan = new NpcDayPlan
        {
            operation_id = message.operation_id,
            npc_id = message.npc_id,
            game_day = message.game_day,
            plan_revision = message.plan_revision,
            planner_version = message.planner_version,
            segments = message.segments ?? new List<NpcPlanSegmentDefinition>(),
            work_tasks = message.work_tasks ?? new List<NpcPlannedTask>(),
            rest_tasks = message.rest_tasks ?? new List<NpcPlannedTask>(),
        };
        if (!_plans.TryGetValue(message.npc_id, out NpcDayPlanRuntime runtime))
            _plans[message.npc_id] = runtime = new NpcDayPlanRuntime();
        if (runtime.GameDay > 0 && plan.game_day > runtime.GameDay)
        {
            _behaviorApplier?.CancelScheduleTasks("previous_day_plan_retired");
            _taskByRequest.Clear();
        }
        if (!runtime.AcceptPlan(plan, out string reason))
        {
            Debug.LogWarning($"[NpcDayPlan] 拒绝 npc={message.npc_id} reason={reason}");
            return;
        }
        StartActiveTask(runtime);
    }

    /// <summary>在权威分钟只发送 17:00 与午夜边界，并尝试启动 runtime 当前任务。</summary>
    public void Tick(GameTime gameTime)
    {
        if (gameTime == null) return;
        if (_lastBoundaryDay != gameTime.day)
        {
            _lastBoundaryDay = gameTime.day;
            _workBoundarySent = false;
            _dayBoundarySent = false;
        }
        if (!_workBoundarySent && gameTime.hour >= 17)
        {
            _workBoundarySent = true;
            foreach (NpcDayPlanRuntime runtime in _plans.Values)
                if (runtime.GameDay == gameTime.day) runtime.OnSegmentBoundary("work_end", out _);
        }
        if (!_dayBoundarySent && gameTime.hour == 0 && gameTime.minute == 0)
        {
            _dayBoundarySent = true;
            foreach (NpcDayPlanRuntime runtime in _plans.Values)
                if (runtime.GameDay < gameTime.day) runtime.OnSegmentBoundary("day_end", out _);
            _behaviorApplier?.CancelScheduleTasks("forced_terminal_at_day_boundary");
            _taskByRequest.Clear();
        }
        foreach (NpcDayPlanRuntime runtime in _plans.Values) StartActiveTask(runtime);
    }

    /// <summary>旧分钟 controller 查询已退役，始终返回 false。</summary>
    public bool TryGet(string npcId, out NpcDailyScheduleController schedule)
    {
        schedule = null;
        return false;
    }

    /// <summary>导出兼容诊断 DTO，字段语义来自两段式 runtime。</summary>
    public List<NpcDailyScheduleDiagnosticSnapshot> Diagnostics()
    {
        var result = new List<NpcDailyScheduleDiagnosticSnapshot>();
        foreach (KeyValuePair<string, NpcDayPlanRuntime> pair in _plans)
        {
            NpcDayPlanRuntimeSnapshot snapshot = pair.Value.CreateSnapshot();
            result.Add(new NpcDailyScheduleDiagnosticSnapshot
            {
                npc_id = pair.Key, schedule_day = snapshot.game_day, schedule_revision = snapshot.plan_revision,
                planner_version = snapshot.planner_version,
                remaining_count = snapshot.remaining_work_count + snapshot.remaining_rest_count,
                pending_candidate_id = snapshot.active_task?.candidate_id ?? string.Empty,
                last_decision_reason = snapshot.last_boundary_reason,
                payload_fingerprint = pair.Value.AcceptedFingerprint,
                last_operation_id = snapshot.last_mutation_operation_id,
                last_replan_operation_id = string.Empty, last_replan_status = "retired",
            });
        }
        return result;
    }

    /// <summary>导出正式 day plan 结构化快照。</summary>
    public List<NpcDayPlanRuntimeSnapshot> DayPlanSnapshots()
    {
        var result = new List<NpcDayPlanRuntimeSnapshot>();
        foreach (NpcDayPlanRuntime runtime in _plans.Values) result.Add(runtime.CreateSnapshot());
        return result;
    }

    /// <summary>把稳定计划身份、活动段和两个剩余队列写入主存档。</summary>
    public void WriteToSave(List<NpcWorldSaveData> savedNpcs, int gameDay)
    {
        foreach (NpcWorldSaveData saved in savedNpcs ?? new List<NpcWorldSaveData>())
        {
            if (saved == null || !_plans.TryGetValue(saved.npc_id, out NpcDayPlanRuntime runtime) || runtime.GameDay != gameDay)
            {
                if (saved != null) saved.day_plan = null;
                continue;
            }
            saved.day_plan = runtime.ExportPlan("save_restore");
            saved.schedule_day = 0;
            saved.schedule_revision = 0;
            saved.remaining_daily_schedule = new List<NpcDailyScheduleItem>();
        }
    }

    /// <summary>只恢复新 day plan；旧分钟日程不再进入生产 owner。</summary>
    public void Restore(GameSaveData data)
    {
        _plans.Clear();
        _taskByRequest.Clear();
        if (data?.game_time == null) return;
        foreach (NpcWorldSaveData saved in data.npcs ?? new List<NpcWorldSaveData>())
        {
            if (saved?.day_plan == null || saved.day_plan.game_day != data.game_time.day) continue;
            var runtime = new NpcDayPlanRuntime();
            if (runtime.AcceptPlan(saved.day_plan, out _)) _plans[saved.npc_id] = runtime;
        }
    }

    /// <summary>把 runtime 唯一活动任务提交到 executor seam，重复 Tick 不重复启动。</summary>
    private void StartActiveTask(NpcDayPlanRuntime runtime)
    {
        NpcPlannedTask task = runtime.ActiveTask;
        if (task == null || (_social?.IsReserved(runtime.NpcId) ?? false)) return;
        string requestId = $"dayplan:{runtime.GameDay}:{runtime.PlanRevision}:{task.task_id}";
        if (_taskByRequest.ContainsKey(requestId)) return;
        NpcEntity npc = _getNpc(runtime.NpcId);
        if (npc == null) return;
        _taskByRequest[requestId] = task.task_id;
        _ambient?.CancelAmbient(npc);
        _behaviorApplier.Apply(new NpcTaskCommand
        {
            request_id = requestId, npc_id = runtime.NpcId, candidate_id = task.candidate_id,
            schedule_revision = runtime.PlanRevision,
            behavior = new NpcBehaviorCmd
            {
                action_id = task.action_id, location_id = task.location_id,
                expected_duration_sec = Mathf.Max(0.1f, task.duration_gameplay_seconds *
                    (GameManager.Instance?.SecondsPerGameMinute ?? 1f) / 60f),
                movement_mode = "walk", interruptible = task.interrupt_policy != "non_interruptible",
            },
            context = new BehaviorContext { reason = "day_plan", plan_source = task.source },
        }, npc);
    }

    /// <summary>只有 request 与活动 task 同时匹配时消费终态；失败和取消同样推进队列。</summary>
    private void HandleTaskTerminal(NpcTaskCommand command, string status, string reason)
    {
        if (command == null || !_taskByRequest.Remove(command.request_id, out string taskId)) return;
        if (!_plans.TryGetValue(command.npc_id, out NpcDayPlanRuntime runtime)) return;
        string terminal = status == "succeeded" ? "succeeded" : status == "cancelled" ? "cancelled" : "failed";
        if (runtime.OnTaskTerminal(taskId, terminal, out _)) StartActiveTask(runtime);
    }
}
