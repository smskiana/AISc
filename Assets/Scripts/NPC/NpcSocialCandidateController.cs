using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Unity 权威的 NPC-NPC 物理候选扫描与冷却；Python 仅回答语义意愿。
/// </summary>
public sealed class NpcSocialCandidateController : MonoBehaviour
{
    private const int CooldownMinutes = 60;
    private const int PendingTimeoutMinutes = 3;
    private readonly Dictionary<string, PendingCandidate> _pending = new();
    private readonly HashSet<string> _pendingPairs = new();
    private readonly Dictionary<string, int> _cooldownUntil = new();
    private NpcSpawner _spawner;
    private GameManager _gameManager;
    public event Func<NpcSocialDecisionResultMsg, string, bool> AcceptedDecision;

    private sealed class PendingCandidate
    {
        public string NpcId;
        public string TargetNpcId;
        public string LocationId;
        public string PairKey;
        public int RequestedAtMinute;
        public long WorldRevision;
    }

    /// <summary>
    /// 绑定已存在的 NPC 托管器和协议回调，不依赖场景新增引用。
    /// </summary>
    public void Initialize(NpcSpawner spawner)
    {
        _spawner = spawner;
        _gameManager = GameManager.Instance;
        if (_gameManager == null)
            return;
        _gameManager.OnAuthoritativeGameTimeChanged += Scan;
        if (_gameManager.WS?.Callbacks != null)
        {
            _gameManager.WS.Callbacks.OnNpcSocialDecisionResult += HandleDecision;
        }
    }

    /// <summary>
    /// 释放运行时订阅，避免跨场景遗留候选。
    /// </summary>
    private void OnDestroy()
    {
        if (_gameManager == null)
            return;
        _gameManager.OnAuthoritativeGameTimeChanged -= Scan;
        if (_gameManager.WS?.Callbacks != null)
        {
            _gameManager.WS.Callbacks.OnNpcSocialDecisionResult -= HandleDecision;
        }
    }

    /// <summary>
    /// 每个 Unity 权威分钟扫描同 zone、可见且可切换的 NPC 配对。
    /// </summary>
    private void Scan(GameTime gameTime)
    {
        if (_spawner == null || _gameManager == null || !_gameManager.IsGameplayReady || gameTime == null)
            return;
        var npcs = new List<NpcEntity>(_spawner.GetAllNpcs());
        int absoluteMinute = (gameTime.day - 1) * 1440 + gameTime.hour * 60 + gameTime.minute;
        RemoveExpiredPending(absoluteMinute);
        for (int index = 0; index < npcs.Count; index++)
        {
            for (int next = index + 1; next < npcs.Count; next++)
            {
                NpcEntity first = npcs[index];
                NpcEntity second = npcs[next];
                if (!IsPhysicalCandidate(first, second))
                    continue;
                string pairKey = BuildPairKey(first.NpcId, second.NpcId);
                if (_cooldownUntil.TryGetValue(pairKey, out int until) && absoluteMinute < until)
                    continue;
                if (_pendingPairs.Contains(pairKey))
                    continue;
                string candidateId = $"social:{gameTime.day}:{gameTime.hour:D2}{gameTime.minute:D2}:{pairKey}";
                if (_pending.ContainsKey(candidateId))
                    continue;
                _pending[candidateId] = new PendingCandidate
                {
                    NpcId = first.NpcId,
                    TargetNpcId = second.NpcId,
                    LocationId = first.CurrentLocation,
                    PairKey = pairKey,
                    RequestedAtMinute = absoluteMinute,
                    WorldRevision = _gameManager.WorldRevision,
                };
                _pendingPairs.Add(pairKey);
                _gameManager.SendNpcSocialDecisionRequest(candidateId, candidateId, first.NpcId, second.NpcId, first.CurrentLocation);
            }
        }
    }

    /// <summary>
    /// 只有双方仍在原地、未移动/锁定且处于玩家当前 zone 时才接受迟到的意愿结果。
    /// </summary>
    private void HandleDecision(NpcSocialDecisionResultMsg result)
    {
        if (result == null || !_pending.TryGetValue(result.candidate_id, out PendingCandidate pending))
            return;
        _pending.Remove(result.candidate_id);
        _pendingPairs.Remove(pending.PairKey);
        NpcEntity first = _spawner?.GetNpc(pending.NpcId);
        NpcEntity second = _spawner?.GetNpc(pending.TargetNpcId);
        if (!result.want_to_talk || result.world_revision != pending.WorldRevision || !IsPhysicalCandidate(first, second))
            return;
        bool started = false;
        if (AcceptedDecision != null)
        {
            foreach (Func<NpcSocialDecisionResultMsg, string, bool> handler in AcceptedDecision.GetInvocationList())
                started |= handler(result, pending.LocationId);
        }
        if (!started)
            return;
        GameTime now = _gameManager.CurrentTime;
        _cooldownUntil[pending.PairKey] = (now.day - 1) * 1440 + now.hour * 60 + now.minute + CooldownMinutes;
    }

    /// <summary>
    /// 查询 NPC 是否已经被 Unity 社交 session 原子 reservation 占用。
    /// </summary>
    public bool IsReserved(string npcId)
    {
        return NpcSocialProtocolController.IsNpcReserved(npcId);
    }

    /// <summary>
    /// 清理迟迟没有语义结果的候选，防止同一对 NPC 被永久 pending 或每分钟洪泛请求。
    /// </summary>
    private void RemoveExpiredPending(int absoluteMinute)
    {
        var expired = new List<string>();
        foreach (var pair in _pending)
        {
            if (absoluteMinute - pair.Value.RequestedAtMinute >= PendingTimeoutMinutes)
                expired.Add(pair.Key);
        }
        foreach (string candidateId in expired)
        {
            PendingCandidate pending = _pending[candidateId];
            _pending.Remove(candidateId);
            _pendingPairs.Remove(pending.PairKey);
        }
    }

    /// <summary>
    /// 过滤 transit、移动、锁定、不同 zone 与玩家不可见的候选。
    /// </summary>
    private bool IsPhysicalCandidate(NpcEntity first, NpcEntity second)
    {
        if (first == null || second == null || first.IsMoving || second.IsMoving || first.IsMotionLocked || second.IsMotionLocked)
            return false;
        if (string.IsNullOrEmpty(first.CurrentLocation) || first.CurrentLocation.StartsWith("__transit__:", StringComparison.Ordinal))
            return false;
        string zone = ZoneOf(first.CurrentLocation);
        return zone == ZoneOf(second.CurrentLocation) && zone == ZoneOf(_gameManager.PlayerLocation);
    }

    /// <summary>
    /// 从共享 location ID 得到稳定 zone，不猜测不存在的物理位置。
    /// </summary>
    private static string ZoneOf(string locationId)
    {
        int separator = string.IsNullOrEmpty(locationId) ? -1 : locationId.IndexOf('.');
        return separator > 0 ? locationId.Substring(0, separator) : string.Empty;
    }

    /// <summary>
    /// 为冷却生成无方向的稳定 NPC 对标识。
    /// </summary>
    private static string BuildPairKey(string first, string second)
    {
        return string.CompareOrdinal(first, second) < 0 ? $"{first}:{second}" : $"{second}:{first}";
    }
}
