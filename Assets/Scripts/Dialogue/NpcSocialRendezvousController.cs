using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 控制 NPC-NPC 社交对话前的靠近、等待与移动锁。
/// </summary>
public class NpcSocialRendezvousController
{
    private readonly NpcSpawner _npcSpawner;
    private readonly float _maxNpcDialogueDistance;
    private readonly float _npcDialogueWaitTimeoutSec;
    private readonly float _npcDialogueRetryIntervalSec;
    private readonly Dictionary<string, List<string>> _lockedConversationNpcIds = new();

    public float WaitTimeoutSec => Mathf.Max(0.5f, _npcDialogueWaitTimeoutSec);
    public float RetryIntervalSec => Mathf.Max(0.1f, _npcDialogueRetryIntervalSec);

    public NpcSocialRendezvousController(
        NpcSpawner npcSpawner,
        float maxNpcDialogueDistance,
        float npcDialogueWaitTimeoutSec,
        float npcDialogueRetryIntervalSec)
    {
        _npcSpawner = npcSpawner;
        _maxNpcDialogueDistance = maxNpcDialogueDistance;
        _npcDialogueWaitTimeoutSec = npcDialogueWaitTimeoutSec;
        _npcDialogueRetryIntervalSec = npcDialogueRetryIntervalSec;
    }

    /// <summary>
    /// 应用 NPC 社交动作，让参与者朝同一地点靠近并播放动作。
    /// </summary>
    public void ApplySocialAction(NpcSocialActionMsg msg)
    {
        var npcA = _npcSpawner.GetNpc(msg.npc_id);
        var npcB = _npcSpawner.GetNpc(msg.target_npc_id);

        if (npcA != null)
        {
            MoveNpcToSocialLocation(npcA, msg.location_id);
            npcA.PlayAction(msg.action_id);
        }

        if (npcB != null)
        {
            MoveNpcToSocialLocation(npcB, msg.location_id);
            npcB.PlayAction(msg.action_id);
        }

        Debug.Log($"[BubbleMgr] 社交动作: {msg.npc_id} → {msg.target_npc_id} [{msg.action_id}] @ {msg.location_id}");
    }

    /// <summary>
    /// 判断 NPC-NPC 气泡是否需要等待双方靠近。
    /// </summary>
    public bool ShouldWaitForParticipants(string speakerNpcId, string targetNpcId)
    {
        if (string.IsNullOrEmpty(targetNpcId))
            return false;

        var speaker = _npcSpawner.GetNpc(speakerNpcId);
        var target = _npcSpawner.GetNpc(targetNpcId);
        if (speaker == null || target == null)
            return false;

        float maxDistance = Mathf.Max(0.1f, _maxNpcDialogueDistance);
        return Vector2.Distance(speaker.transform.position, target.transform.position) > maxDistance;
    }

    /// <summary>
    /// NPC 世界气泡对话开始显示后，锁定双方移动。
    /// </summary>
    public void LockConversationParticipants(string conversationKey, string speakerNpcId, string targetNpcId)
    {
        if (_lockedConversationNpcIds.ContainsKey(conversationKey))
            return;

        var ids = new List<string>();
        AddNpcIdIfPresent(ids, speakerNpcId);
        AddNpcIdIfPresent(ids, targetNpcId);

        string lockReason = BuildConversationLockReason(conversationKey);
        foreach (var npcId in ids)
        {
            var npc = _npcSpawner.GetNpc(npcId);
            if (npc != null)
                npc.PushMotionLock(lockReason);
        }

        _lockedConversationNpcIds[conversationKey] = ids;
    }

    /// <summary>
    /// 一组世界气泡对话播完或被清理时释放双方移动锁。
    /// </summary>
    public void ReleaseConversationLock(string conversationKey)
    {
        if (!_lockedConversationNpcIds.TryGetValue(conversationKey, out var ids))
            return;

        string lockReason = BuildConversationLockReason(conversationKey);
        foreach (var npcId in ids)
        {
            var npc = _npcSpawner.GetNpc(npcId);
            if (npc != null)
                npc.PopMotionLock(lockReason);
        }

        _lockedConversationNpcIds.Remove(conversationKey);
    }

    /// <summary>
    /// NPC 社交动作发生时，先让参与者朝同一个地点靠近。
    /// </summary>
    private void MoveNpcToSocialLocation(NpcEntity npc, string locationId)
    {
        if (npc == null || string.IsNullOrWhiteSpace(locationId))
            return;

        if (!LocationDatabase.HasPosition(locationId))
            return;

        npc.MoveToLocation(locationId);
    }

    /// <summary>
    /// 去重添加非空 NPC ID。
    /// </summary>
    private void AddNpcIdIfPresent(List<string> ids, string npcId)
    {
        if (string.IsNullOrEmpty(npcId) || ids.Contains(npcId))
            return;

        ids.Add(npcId);
    }

    /// <summary>
    /// 构造移动锁 reason，确保同一对话可重复加锁/解锁。
    /// </summary>
    private string BuildConversationLockReason(string conversationKey)
    {
        return $"npc_dialogue:{conversationKey}";
    }
}
