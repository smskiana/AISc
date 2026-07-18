using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Unity 权威托管 NPC-NPC reservation、会合、内容等待、播放与终态。
/// </summary>
public sealed class NpcSocialProtocolController
{
    private const float RendezvousTimeoutSec = 120f;
    private const float ContentTimeoutSec = 120f;
    private const float PlaybackTimeoutSec = 180f;
    private static readonly NpcSocialReservationTable Reservations = new();
    private readonly MonoBehaviour _coroutineHost;
    private readonly NpcSpawner _npcSpawner;
    private readonly NpcSocialRendezvousController _rendezvous;
    private readonly Dictionary<string, ActiveSession> _active = new();
    private readonly List<NpcSocialDiagnosticSnapshot> _recent = new();
    public static NpcSocialProtocolController ActiveInstance { get; private set; }

    private sealed class ActiveSession
    {
        public string RequestId;
        public string CandidateId;
        public string NpcA;
        public string NpcB;
        public string LocationId;
        public string State;
        public bool NpcACompleted;
        public bool NpcBCompleted;
        public MovementResult NpcAResult;
        public MovementResult NpcBResult;
        public long ContentWorldRevision;
        public Coroutine TimeoutRoutine;
    }

    /// <summary>
    /// 绑定协程宿主、NPC 查询和会合距离判断。
    /// </summary>
    public NpcSocialProtocolController(MonoBehaviour coroutineHost, NpcSpawner npcSpawner, NpcSocialRendezvousController rendezvous)
    {
        _coroutineHost = coroutineHost;
        _npcSpawner = npcSpawner;
        _rendezvous = rendezvous;
        ActiveInstance = this;
    }

    /// <summary>
    /// 原子获取双方 reservation，并由 Unity 主动启动会合。
    /// </summary>
    public bool Begin(NpcSocialDecisionResultMsg decision, string locationId)
    {
        if (decision == null || string.IsNullOrWhiteSpace(decision.request_id))
            return false;
        NpcEntity npcA = _npcSpawner?.GetNpc(decision.npc_id);
        NpcEntity npcB = _npcSpawner?.GetNpc(decision.target_npc_id);
        if (npcA == null || npcB == null || npcA.IsMotionLocked || npcB.IsMotionLocked)
            return false;
        if (!LocationDatabase.HasPosition(locationId))
            return false;
        if (!Reservations.TryReserve(decision.request_id, decision.npc_id, decision.target_npc_id))
            return false;
        var session = new ActiveSession
        {
            RequestId = decision.request_id,
            CandidateId = decision.candidate_id,
            NpcA = decision.npc_id,
            NpcB = decision.target_npc_id,
            LocationId = locationId,
            State = "rendezvous",
        };
        _active[session.RequestId] = session;
        SetTimeout(session, RendezvousTimeoutSec);
        npcA.MoveToLocation(locationId, result => HandleMovementResult(session.RequestId, true, result));
        npcB.MoveToLocation(locationId, result => HandleMovementResult(session.RequestId, false, result));
        return true;
    }

    /// <summary>
    /// 接受与当前内容请求 revision 匹配的结果，进入播放阶段。
    /// </summary>
    public bool TryAcceptContent(NpcSocialContentResultMsg result)
    {
        if (result == null || !_active.TryGetValue(result.request_id, out ActiveSession session))
            return false;
        if (session.State != "awaiting_content" || result.world_revision != session.ContentWorldRevision)
            return false;
        if (!result.success || result.lines == null || result.lines.Count == 0)
        {
            Fail(session.RequestId, string.IsNullOrEmpty(result.reason) ? "content_failed" : result.reason);
            return false;
        }
        session.State = "playback";
        SetTimeout(session, PlaybackTimeoutSec);
        return true;
    }

    /// <summary>
    /// 判断 request 是否正在等待或播放 Unity 权威社交 session。
    /// </summary>
    public bool IsPrepared(string requestId)
    {
        return !string.IsNullOrEmpty(requestId) && _active.ContainsKey(requestId);
    }

    /// <summary>
    /// 查询 NPC 是否被任一社交 session reservation 占用。
    /// </summary>
    public static bool IsNpcReserved(string npcId)
    {
        return Reservations.IsReserved(npcId);
    }

    /// <summary>
    /// 导出活动阶段与最近终态，供 aisc_debug 稳定读取。
    /// </summary>
    public List<NpcSocialDiagnosticSnapshot> GetDiagnosticSnapshots()
    {
        var snapshots = new List<NpcSocialDiagnosticSnapshot>(_recent);
        foreach (ActiveSession session in _active.Values)
            snapshots.Add(CreateSnapshot(session, false, string.Empty));
        return snapshots;
    }

    /// <summary>
    /// 最后一句播放结束后提交 COMPLETE 并释放双方占用。
    /// </summary>
    public void CompletePlayback(string requestId, string npcId, string targetNpcId)
    {
        if (!_active.TryGetValue(requestId, out ActiveSession session) || session.State != "playback")
            return;
        GameManager gm = GameManager.Instance;
        gm?.SendNpcSocialComplete(requestId, npcId, targetNpcId, ResolveActualLocation(session));
        session.State = "completed";
        RecordTerminal(session, "completed");
        Release(requestId);
    }

    /// <summary>
    /// 玩家对话等高优先级交互按 NPC 取消本地 session。
    /// </summary>
    public void CancelForNpc(string npcId, string reason)
    {
        if (!Reservations.TryGetRequest(npcId, out string requestId))
            return;
        Fail(requestId, reason);
    }

    /// <summary>
    /// 气泡播放异常时提交 FAILED 并释放双方占用。
    /// </summary>
    public void FailPlayback(string requestId, string npcId, string targetNpcId, string reason)
    {
        Fail(requestId, reason);
    }

    /// <summary>
    /// 接收双方真实移动终态，成功会合后请求 Python 内容。
    /// </summary>
    private void HandleMovementResult(string requestId, bool isNpcA, MovementResult result)
    {
        if (!_active.TryGetValue(requestId, out ActiveSession session) || session.State != "rendezvous")
            return;
        if (isNpcA) { session.NpcACompleted = true; session.NpcAResult = result; }
        else { session.NpcBCompleted = true; session.NpcBResult = result; }
        if (!session.NpcACompleted || !session.NpcBCompleted)
            return;
        if (session.NpcAResult != MovementResult.Succeeded || session.NpcBResult != MovementResult.Succeeded)
        {
            Fail(requestId, "movement_failed");
            return;
        }
        if (_rendezvous.ShouldWaitForParticipants(session.NpcA, session.NpcB))
        {
            Fail(requestId, "rendezvous_distance_not_met");
            return;
        }
        GameManager gm = GameManager.Instance;
        session.State = "awaiting_content";
        session.ContentWorldRevision = gm != null ? gm.WorldRevision : 0;
        SetTimeout(session, ContentTimeoutSec);
        gm?.SendNpcSocialContentRequest(requestId, session.CandidateId, session.NpcA, session.NpcB, ResolveActualLocation(session), gm.CurrentTime, session.ContentWorldRevision);
    }

    /// <summary>
    /// 替换当前阶段的 Unity 本地监督协程。
    /// </summary>
    private void SetTimeout(ActiveSession session, float timeoutSec)
    {
        if (session.TimeoutRoutine != null)
            _coroutineHost.StopCoroutine(session.TimeoutRoutine);
        string expectedState = session.State;
        session.TimeoutRoutine = _coroutineHost.StartCoroutine(TimeoutAfter(session.RequestId, expectedState, timeoutSec));
    }

    /// <summary>
    /// 由 Unity 释放超时 reservation，Python 不监督运行时阶段。
    /// </summary>
    private IEnumerator TimeoutAfter(string requestId, string expectedState, float timeoutSec)
    {
        yield return new WaitForSecondsRealtime(timeoutSec);
        if (_active.TryGetValue(requestId, out ActiveSession session) && session.State == expectedState)
            Fail(requestId, $"{expectedState}_timeout");
    }

    /// <summary>
    /// 提交稳定失败原因并统一释放 session。
    /// </summary>
    private void Fail(string requestId, string reason)
    {
        if (!_active.TryGetValue(requestId, out ActiveSession session))
            return;
        GameManager.Instance?.SendNpcSocialFailed(requestId, session.NpcA, session.NpcB, ResolveActualLocation(session), reason);
        RecordTerminal(session, reason);
        Release(requestId);
    }

    /// <summary>
    /// 停止监督并原子释放双方 reservation。
    /// </summary>
    private void Release(string requestId)
    {
        if (!_active.TryGetValue(requestId, out ActiveSession session))
            return;
        if (session.TimeoutRoutine != null)
            _coroutineHost.StopCoroutine(session.TimeoutRoutine);
        Reservations.Release(requestId, session.NpcA, session.NpcB);
        _active.Remove(requestId);
    }

    /// <summary>
    /// 返回双方确认的共同逻辑地点。
    /// </summary>
    private string ResolveActualLocation(ActiveSession session)
    {
        NpcEntity npcA = _npcSpawner?.GetNpc(session.NpcA);
        NpcEntity npcB = _npcSpawner?.GetNpc(session.NpcB);
        return npcA != null && npcA.CurrentLocation == npcB?.CurrentLocation ? npcA.CurrentLocation : session.LocationId;
    }

    /// <summary>
    /// 记录有限数量的稳定终态，避免诊断缓存无限增长。
    /// </summary>
    private void RecordTerminal(ActiveSession session, string reason)
    {
        _recent.Add(CreateSnapshot(session, true, reason));
        if (_recent.Count > 20)
            _recent.RemoveAt(0);
    }

    /// <summary>
    /// 将内部 session 转成不暴露可写状态的诊断 DTO。
    /// </summary>
    private static NpcSocialDiagnosticSnapshot CreateSnapshot(ActiveSession session, bool terminal, string reason)
    {
        return new NpcSocialDiagnosticSnapshot
        {
            request_id = session.RequestId,
            candidate_id = session.CandidateId,
            npc_id = session.NpcA,
            target_npc_id = session.NpcB,
            location_id = session.LocationId,
            phase = terminal ? "terminal" : session.State,
            terminal_reason = reason,
            is_terminal = terminal,
            world_revision = session.ContentWorldRevision,
        };
    }
}

/// <summary>
/// 提供无 Unity 对象依赖的双方原子 reservation 语义。
/// </summary>
public sealed class NpcSocialReservationTable
{
    private readonly Dictionary<string, string> _requestByNpc = new();

    /// <summary>
    /// 仅在双方都空闲时一次性占用，失败不得留下单边 reservation。
    /// </summary>
    public bool TryReserve(string requestId, string npcA, string npcB)
    {
        if (string.IsNullOrWhiteSpace(requestId) || string.IsNullOrWhiteSpace(npcA)
            || string.IsNullOrWhiteSpace(npcB) || npcA == npcB)
            return false;
        if (_requestByNpc.ContainsKey(npcA) || _requestByNpc.ContainsKey(npcB))
            return false;
        _requestByNpc[npcA] = requestId;
        _requestByNpc[npcB] = requestId;
        return true;
    }

    /// <summary>
    /// 查询 NPC 是否已被 reservation 占用。
    /// </summary>
    public bool IsReserved(string npcId)
    {
        return !string.IsNullOrEmpty(npcId) && _requestByNpc.ContainsKey(npcId);
    }

    /// <summary>
    /// 返回指定 NPC 当前 reservation 的 request ID。
    /// </summary>
    public bool TryGetRequest(string npcId, out string requestId)
    {
        return _requestByNpc.TryGetValue(npcId, out requestId);
    }

    /// <summary>
    /// 只释放属于当前 request 的双方记录，避免迟到终态释放新 session。
    /// </summary>
    public void Release(string requestId, string npcA, string npcB)
    {
        ReleaseOne(requestId, npcA);
        ReleaseOne(requestId, npcB);
    }

    /// <summary>
    /// 按 request 所有权释放单名 NPC。
    /// </summary>
    private void ReleaseOne(string requestId, string npcId)
    {
        if (_requestByNpc.TryGetValue(npcId, out string owner) && owner == requestId)
            _requestByNpc.Remove(npcId);
    }
}
