using System;

/// <summary>
/// 统一维护世界准备诊断快照，并以 operation 身份约束进度与终态转换。
/// </summary>
public sealed class WorldPreparationStateTracker
{
    public WorldPreparationDiagnosticSnapshot Snapshot { get; private set; } =
        new WorldPreparationDiagnosticSnapshot();

    /// <summary>
    /// 接收进度并建立或推进活动 operation；已终态 operation 不会被迟到进度复活。
    /// </summary>
    public bool TryApplyProgress(WorldPreparationProgressMsg message)
    {
        if (message == null || string.IsNullOrEmpty(message.operation_id))
            return false;

        if (!Snapshot.is_active &&
            string.Equals(Snapshot.operation_id, message.operation_id, StringComparison.Ordinal))
        {
            return false;
        }

        if (Snapshot.is_active &&
            !string.Equals(Snapshot.operation_id, message.operation_id, StringComparison.Ordinal))
        {
            return false;
        }

        Snapshot = new WorldPreparationDiagnosticSnapshot
        {
            operation_id = message.operation_id,
            flow = message.flow ?? string.Empty,
            phase = message.phase ?? string.Empty,
            is_active = true,
            progress_floor = Math.Max(Snapshot.progress_floor, message.progress_floor),
            failure_reason = string.Empty,
            target_game_day = message.target_game_day,
        };
        return true;
    }

    /// <summary>
    /// 仅用匹配的终包完成当前活动 operation。
    /// </summary>
    public bool TryComplete(string operationId)
    {
        if (!MatchesActiveOperation(operationId))
            return false;

        Snapshot.phase = "complete";
        Snapshot.is_active = false;
        Snapshot.progress_floor = 1f;
        Snapshot.failure_reason = string.Empty;
        return true;
    }

    /// <summary>
    /// 仅用匹配的终包失败当前活动 operation，并保留已达到的进度。
    /// </summary>
    public bool TryFail(string operationId, string reason)
    {
        if (!MatchesActiveOperation(operationId))
            return false;

        Snapshot.phase = "failed";
        Snapshot.is_active = false;
        Snapshot.failure_reason = reason ?? string.Empty;
        return true;
    }

    /// <summary>
    /// 判断终包是否属于当前活动 operation。
    /// </summary>
    private bool MatchesActiveOperation(string operationId)
    {
        return Snapshot.is_active &&
               !string.IsNullOrEmpty(operationId) &&
               string.Equals(Snapshot.operation_id, operationId, StringComparison.Ordinal);
    }
}
