using UnityEngine;

/// <summary>
/// 将 Unity 内部 NPC 任务命令应用到前端 NPC 实体。
/// </summary>
public class NpcBehaviorApplier
{
    private readonly NpcActionResultReporter _resultReporter;
    private readonly NpcTaskExecutor _taskExecutor;

    public NpcBehaviorApplier(NpcActionResultReporter resultReporter)
    {
        _resultReporter = resultReporter;
        _taskExecutor = new NpcTaskExecutor(resultReporter);
    }

    /// <summary>
    /// 根据行为消息驱动 NPC 移动、动作表现和关键日志。
    /// </summary>
    public void Apply(NpcTaskCommand msg, NpcEntity npc)
    {
        if (npc == null)
        {
            Debug.LogWarning($"[NpcBehaviorApplier] NPC 不存在: {msg.npc_id}");
            _resultReporter?.Report(msg, MovementResult.Failed, string.Empty, "npc_not_found");
            return;
        }

        var behavior = msg.behavior;
        if (behavior == null)
        {
            _resultReporter?.Report(msg, MovementResult.Failed, npc.CurrentLocation, "behavior_missing");
            return;
        }

        // 移动类 action 统一走实体移动入口。
        // 当前由任务执行器统一决定是否需要移动，不再通过 action_id 分支。
        _taskExecutor.Execute(msg, npc);

        var reason = msg.context?.reason ?? "";
        if (ShouldLogImportantDecision(reason))
            Debug.Log($"[行为] {npc.NpcName}({msg.npc_id}) → {behavior.action_id} @ {behavior.location_id} ({reason})");
    }

    /// <summary>
    /// 取消全部正式任务并将当日剩余执行视为结束。
    /// </summary>
    public void CancelAll(string reason)
    {
        _taskExecutor.CancelAll(reason);
    }

    /// <summary>跨日换代时取消旧日活动任务，不施加睡眠流程锁。</summary>
    public void CancelScheduleTasks(string reason)
    {
        _taskExecutor.CancelScheduleTasks(reason);
    }

    /// <summary>
    /// 返回正式任务执行器的只读诊断快照。
    /// </summary>
    public System.Collections.Generic.List<NpcTaskDiagnosticSnapshot> GetTaskDiagnosticSnapshots()
    {
        return _taskExecutor.GetDiagnosticSnapshots();
    }

    /// <summary>
    /// 仅输出 P0/P2/P4 等重要行为决策日志。
    /// </summary>
    private bool ShouldLogImportantDecision(string reason)
    {
        return reason.StartsWith("P0")
            || reason.StartsWith("P2")
            || reason.StartsWith("P4");
    }
}

/// <summary>
/// 将 Unity 场景中的 NPC 行为执行结果转换为稳定协议并回传后端。
/// </summary>
public class NpcActionResultReporter
{
    public event System.Action<NpcTaskCommand, string, string> TerminalReported;
    private readonly GameManager _gameManager;

    public NpcActionResultReporter(GameManager gameManager)
    {
        _gameManager = gameManager;
    }

    /// <summary>
    /// 回报行为结果；缺少 request_id 的旧协议消息只记录警告，不发送无关联结果。
    /// </summary>
    public void Report(NpcTaskCommand msg, MovementResult result, string actualLocationId, string reason = "")
    {
        if (msg == null || string.IsNullOrWhiteSpace(msg.request_id))
        {
            Debug.LogWarning("[NpcActionResultReporter] 行为消息缺少 request_id，无法回报执行结果");
            return;
        }

        _gameManager?.SendNpcRuntimeEvent(
            $"{msg.request_id}:terminal:{ToProtocolStatus(result)}",
            msg.request_id,
            msg.npc_id,
            msg.behavior?.action_id ?? string.Empty,
            ToProtocolStatus(result),
            actualLocationId ?? string.Empty,
            reason ?? string.Empty,
            "terminal",
            msg.candidate_id ?? string.Empty,
            msg.schedule_revision);
    }

    /// <summary>
    /// 回报由前端任务状态机确认的固定终态。
    /// </summary>
    public void ReportStatus(NpcTaskCommand msg, string status, string actualLocationId, string reason = "")
    {
        if (msg == null || string.IsNullOrWhiteSpace(msg.request_id))
            return;

        _gameManager?.SendNpcRuntimeEvent(
            $"{msg.request_id}:terminal:{status}",
            msg.request_id,
            msg.npc_id,
            msg.behavior?.action_id ?? string.Empty,
            status,
            actualLocationId ?? string.Empty,
            reason ?? string.Empty,
            "terminal",
            msg.candidate_id ?? string.Empty,
            msg.schedule_revision);
        TerminalReported?.Invoke(msg, status, reason ?? string.Empty);
    }

    /// <summary>
    /// 非阻塞回报 Unity 已确认的任务执行阶段，不改变后端玩法事实。
    /// </summary>
    public void ReportPhase(NpcTaskCommand msg, string phase, string actualLocationId)
    {
        if (msg == null || string.IsNullOrWhiteSpace(msg.request_id))
            return;
        _gameManager?.SendNpcRuntimeEvent(
            $"{msg.request_id}:{phase}", msg.request_id, msg.npc_id,
            msg.behavior?.action_id ?? string.Empty, string.Empty,
            actualLocationId ?? string.Empty, string.Empty, phase,
            msg.candidate_id ?? string.Empty, msg.schedule_revision);
    }

    /// <summary>
    /// 把前端移动枚举映射为协议固定状态字符串。
    /// </summary>
    private string ToProtocolStatus(MovementResult result) => result switch
    {
        MovementResult.Succeeded => "succeeded",
        MovementResult.Cancelled => "cancelled",
        _ => "failed",
    };
}
