using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>托管日程重规划的单飞、匹配终态、超时和跨日取消。</summary>
public sealed class NpcScheduleReplanTracker
{
    private readonly Dictionary<string, NpcScheduleReplanPending> _pending = new();
    private readonly Dictionary<string, NpcScheduleReplanTerminal> _terminal = new();
    private readonly Func<float> _now;
    private readonly float _timeoutSeconds;

    public NpcScheduleReplanTracker(Func<float> now = null, float timeoutSeconds = 135f)
    {
        _now = now ?? (() => Time.realtimeSinceStartup);
        _timeoutSeconds = timeoutSeconds;
    }

    /// <summary>以 NPC、游戏日和 base revision 为身份原子创建 pending。</summary>
    public bool TryBegin(string npcId, int gameDay, long baseRevision, NpcScheduleSnapshotReference snapshot, GameTime gameTime, out NpcScheduleReplanPending pending, out string reason)
    {
        Expire(npcId);
        if (snapshot == null || string.IsNullOrWhiteSpace(snapshot.snapshot_id) || snapshot.game_day != gameDay)
        {
            pending = null;
            reason = "schedule_snapshot_reference_missing";
            RecordTerminal(npcId, string.Empty, gameDay, baseRevision, reason);
            return false;
        }
        if (_pending.TryGetValue(npcId, out NpcScheduleReplanPending existing))
        {
            if (existing.game_day == gameDay && existing.base_schedule_revision == baseRevision)
            {
                pending = existing;
                reason = "replan_already_in_flight";
                return false;
            }
            RecordTerminal(npcId, existing.operation_id, existing.game_day, existing.base_schedule_revision, "replan_superseded");
            _pending.Remove(npcId);
        }
        pending = new NpcScheduleReplanPending
        {
            operation_id = $"schedule_replan:{npcId}:{gameDay}:{baseRevision}:{Guid.NewGuid():N}",
            npc_id = npcId,
            game_day = gameDay,
            base_schedule_revision = baseRevision,
            snapshot_id = snapshot.snapshot_id,
            time_revision = snapshot.time_revision,
            world_revision = snapshot.world_revision,
            requested_game_time = gameTime,
            started_realtime = _now(),
            status = "pending",
        };
        _pending[npcId] = pending;
        reason = "replan_pending_created";
        return true;
    }

    /// <summary>只让匹配 operation 的后端终态清除当前 pending。</summary>
    public bool TryAcceptTerminal(NpcDailyScheduleReadyMsg message, out string reason)
    {
        if (message == null || !_pending.TryGetValue(message.npc_id ?? string.Empty, out NpcScheduleReplanPending pending))
        {
            reason = "no_replan_pending";
            return true;
        }
        if (!string.Equals(pending.operation_id, message.operation_id, StringComparison.Ordinal))
        {
            reason = "replan_operation_mismatch";
            return false;
        }
        _pending.Remove(message.npc_id);
        string terminal = message.status == "failed" || message.status == "skipped"
            ? (string.IsNullOrWhiteSpace(message.failure_reason) ? "replan_failed" : message.failure_reason)
            : "replan_accepted";
        RecordTerminal(message.npc_id, message.operation_id, pending.game_day, pending.base_schedule_revision, terminal);
        reason = terminal;
        return true;
    }

    /// <summary>取消指定游戏日以前的 pending，隔离跨日迟到终态。</summary>
    public void CancelBeforeDay(int gameDay)
    {
        foreach (string npcId in new List<string>(_pending.Keys))
        {
            NpcScheduleReplanPending pending = _pending[npcId];
            if (pending.game_day >= gameDay) continue;
            RecordTerminal(npcId, pending.operation_id, pending.game_day, pending.base_schedule_revision, "previous_day_replan_cancelled");
            _pending.Remove(npcId);
        }
    }

    /// <summary>读取 pending 或最近终态，供结构化日程诊断使用。</summary>
    public void GetDiagnostic(string npcId, out string operationId, out string status)
    {
        Expire(npcId);
        if (_pending.TryGetValue(npcId, out NpcScheduleReplanPending pending))
        {
            operationId = pending.operation_id;
            status = "pending";
            return;
        }
        if (_terminal.TryGetValue(npcId, out NpcScheduleReplanTerminal terminal))
        {
            operationId = terminal.operation_id;
            status = terminal.reason;
            return;
        }
        operationId = string.Empty;
        status = "idle";
    }

    /// <summary>清空读档前的运行时 pending，不把临时 operation 带入恢复世界。</summary>
    public void Reset()
    {
        _pending.Clear();
        _terminal.Clear();
    }

    private void Expire(string npcId)
    {
        if (!_pending.TryGetValue(npcId, out NpcScheduleReplanPending pending) || _now() - pending.started_realtime < _timeoutSeconds) return;
        _pending.Remove(npcId);
        RecordTerminal(npcId, pending.operation_id, pending.game_day, pending.base_schedule_revision, "schedule_replan_timeout");
    }

    private void RecordTerminal(string npcId, string operationId, int gameDay, long baseRevision, string reason)
    {
        _terminal[npcId ?? string.Empty] = new NpcScheduleReplanTerminal
        {
            operation_id = operationId ?? string.Empty,
            game_day = gameDay,
            base_schedule_revision = baseRevision,
            reason = reason ?? string.Empty,
        };
    }
}
