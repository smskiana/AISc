using System.Collections;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 编排 NPC 正式任务的移动、动作阶段、终态回报和本地诊断快照。
/// </summary>
public class NpcTaskExecutor
{
    private readonly NpcActionResultReporter _resultReporter;
    private readonly Dictionary<string, ActiveNpcTask> _activeTasks = new();
    private readonly Dictionary<string, ActiveNpcTask> _recentTerminalTasks = new();

    public NpcTaskExecutor(NpcActionResultReporter resultReporter)
    {
        _resultReporter = resultReporter;
    }

    /// <summary>
    /// 启动统一任务；目标不同时先移动，到达后才进入动作阶段。
    /// </summary>
    public void Execute(NpcTaskCommand msg, NpcEntity npc)
    {
        if (_activeTasks.TryGetValue(msg.npc_id, out var previous))
        {
            previous.Cancelled = true;
            _resultReporter.ReportStatus(previous.Message, "cancelled", npc.CurrentLocation, "superseded");
        }

        _recentTerminalTasks.Remove(msg.npc_id);

        var task = new ActiveNpcTask(msg, npc);
        _activeTasks[msg.npc_id] = task;
        Advance(task, "validating");

        string target = msg.behavior.location_id ?? string.Empty;
        string movementMode = string.IsNullOrEmpty(msg.behavior.movement_mode)
            ? "walk"
            : msg.behavior.movement_mode;
        bool needsMovement = movementMode != "none" && npc.CurrentLocation != target;
        if (!needsMovement)
        {
            BeginAction(task);
            return;
        }

        Advance(task, "moving");
        npc.MoveToLocation(target, movementMode, result => OnMovementCompleted(task, result));
    }

    /// <summary>
    /// 取消全部当日任务并回报固定取消终态，供睡眠跨日流程使用。
    /// </summary>
    public void CancelAll(string reason)
    {
        foreach (var task in new List<ActiveNpcTask>(_activeTasks.Values))
        {
            task.Cancelled = true;
            task.Npc.PushMotionLock(PauseSources.SleepFlow);
            _resultReporter.ReportStatus(task.Message, "cancelled", task.Npc.CurrentLocation, reason);
            _recentTerminalTasks[task.Message.npc_id] = task;
        }
        _activeTasks.Clear();
    }

    /// <summary>
    /// 导出当前活动任务和最近终态的只读诊断副本。
    /// </summary>
    public List<NpcTaskDiagnosticSnapshot> GetDiagnosticSnapshots()
    {
        var snapshots = new List<NpcTaskDiagnosticSnapshot>();
        foreach (ActiveNpcTask task in _activeTasks.Values)
            snapshots.Add(CreateDiagnosticSnapshot(task, false));
        foreach (ActiveNpcTask task in _recentTerminalTasks.Values)
            snapshots.Add(CreateDiagnosticSnapshot(task, true));
        return snapshots;
    }

    /// <summary>
    /// 导航终态只决定是否进入动作阶段，不直接把到达当作任务成功。
    /// </summary>
    private void OnMovementCompleted(ActiveNpcTask task, MovementResult result)
    {
        if (!IsCurrent(task) || task.Cancelled)
            return;
        if (result != MovementResult.Succeeded)
        {
            string status = result == MovementResult.Cancelled ? "cancelled" : "failed";
            Finish(task, status, "movement_not_completed");
            return;
        }
        BeginAction(task);
    }

    /// <summary>
    /// 播放任务动作，并由前端协程在表现阶段结束后确认成功。
    /// </summary>
    private void BeginAction(ActiveNpcTask task)
    {
        if (!IsCurrent(task) || task.Cancelled)
            return;
        Advance(task, "performing");
        task.Npc.PlayAction(task.Message.behavior.action_id);
        float duration = Mathf.Max(0.1f, task.Message.behavior.expected_duration_sec);
        task.Npc.StartCoroutine(CompleteAfter(task, duration));
    }

    /// <summary>
    /// 等待前端动作表现完成，期间节点询问仍能观察 performing 状态。
    /// </summary>
    private IEnumerator CompleteAfter(ActiveNpcTask task, float duration)
    {
        yield return new WaitForSeconds(duration);
        if (IsCurrent(task) && !task.Cancelled)
            Finish(task, "succeeded", string.Empty);
    }

    /// <summary>
    /// 记录前端终态并通过独立 reporter 回传后端。
    /// </summary>
    private void Finish(ActiveNpcTask task, string status, string reason)
    {
        Advance(task, status);
        _activeTasks.Remove(task.Message.npc_id);
        _recentTerminalTasks[task.Message.npc_id] = task;
        _resultReporter.ReportStatus(task.Message, status, task.Npc.CurrentLocation, reason);
    }

    /// <summary>
    /// 推进阶段并增加进展版本，供后端识别任务是否持续前进。
    /// </summary>
    private static void Advance(ActiveNpcTask task, string phase)
    {
        task.Phase = phase;
        task.ProgressRevision++;
    }

    /// <summary>
    /// 判断回调对应的仍是该 NPC 当前任务，过滤旧导航和旧协程。
    /// </summary>
    private bool IsCurrent(ActiveNpcTask task)
    {
        return _activeTasks.TryGetValue(task.Message.npc_id, out var current)
            && ReferenceEquals(current, task);
    }

    /// <summary>
    /// 将内部可变任务转换为稳定诊断 DTO。
    /// </summary>
    private static NpcTaskDiagnosticSnapshot CreateDiagnosticSnapshot(ActiveNpcTask task, bool isTerminal)
    {
        return new NpcTaskDiagnosticSnapshot
        {
            npc_id = task.Message.npc_id ?? string.Empty,
            request_id = task.Message.request_id ?? string.Empty,
            action_id = task.Message.behavior?.action_id ?? string.Empty,
            target_location_id = task.Message.behavior?.location_id ?? string.Empty,
            actual_location_id = task.Npc.CurrentLocation ?? string.Empty,
            phase = task.Phase ?? string.Empty,
            progress_revision = task.ProgressRevision,
            motion_locked = task.Npc.IsMotionLocked,
            is_terminal = isTerminal,
        };
    }

    private sealed class ActiveNpcTask
    {
        public readonly NpcTaskCommand Message;
        public readonly NpcEntity Npc;
        public string Phase;
        public int ProgressRevision;
        public bool Cancelled;

        public ActiveNpcTask(NpcTaskCommand message, NpcEntity npc)
        {
            Message = message;
            Npc = npc;
        }
    }
}
