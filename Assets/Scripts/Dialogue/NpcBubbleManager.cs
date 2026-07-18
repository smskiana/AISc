using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// NPC 气泡管理器 — 监听后端消息，路由气泡到对应 NpcEntity。
/// 挂载在场景空 GameObject 上。
///
/// 功能:
///   - 监听 OnNpcBubble → 显示/隐藏气泡
///   - 监听 OnNpcSocialAction → 两个 NPC 面对面 + 变色
///   - 处理气泡排队（同一 NPC 多条气泡按序显示）
/// </summary>
public class NpcBubbleManager : MonoBehaviour
{
    [Header("依赖")]
    [SerializeField] private NpcSpawner _npcSpawner;
    [Header("轮播")]
    [SerializeField] private float _turnTransitionBufferSec = 0.45f;
    [SerializeField] private float _maxNpcDialogueDistance = 2.2f;
    [SerializeField] private float _npcDialogueWaitTimeoutSec = 12f;
    [SerializeField] private float _npcDialogueRetryIntervalSec = 0.5f;

    // 待显示气泡队列: conversation_key → 排队的气泡
    private Dictionary<string, Queue<BubbleEntry>> _queues = new();
    private Dictionary<string, bool> _isShowing = new();  // conversation_key → 正在显示?
    private readonly Dictionary<string, string[]> _conversationParticipants = new();
    private NpcSocialRendezvousController _rendezvousController;
    private NpcSocialProtocolController _socialProtocolController;
    private NpcSocialCandidateController _socialCandidateController;

    private struct BubbleEntry
    {
        public string speakerNpcId;
        public string text;
        public float durationSec;
        public string targetNpcId;
        public string conversationKey;
        public float waitStartedAt;
        public string requestId;
        public int lineIndex;
        public int lineCount;
    }

    // ── 初始化 ──

    void Start()
    {
        if (_npcSpawner == null)
            _npcSpawner = FindObjectOfType<NpcSpawner>();
        _rendezvousController = new NpcSocialRendezvousController(
            _npcSpawner,
            _maxNpcDialogueDistance,
            _npcDialogueWaitTimeoutSec,
            _npcDialogueRetryIntervalSec);
        _socialProtocolController = new NpcSocialProtocolController(this, _npcSpawner, _rendezvousController);
        _socialCandidateController = _npcSpawner != null ? _npcSpawner.GetComponent<NpcSocialCandidateController>() : null;
        if (_socialCandidateController != null)
            _socialCandidateController.AcceptedDecision += HandleAcceptedSocialDecision;

        // 注册回调
        var gm = GameManager.Instance;
        if (gm?.WS?.Callbacks != null)
        {
            gm.WS.Callbacks.OnNpcBubble += HandleNpcBubble;
            gm.WS.Callbacks.OnNpcSocialAction += HandleNpcSocialAction;
            gm.WS.Callbacks.OnNpcSocialContentResult += HandleNpcSocialContentResult;
            gm.OnDialogueStarted += HandlePlayerDialogueStarted;
            gm.OnDialogueEnded += HandlePlayerDialogueEnded;
        }

        Debug.Log("[BubbleMgr] 就绪");
    }

    void OnDestroy()
    {
        var gm = GameManager.Instance;
        if (gm?.WS?.Callbacks != null)
        {
            gm.WS.Callbacks.OnNpcBubble -= HandleNpcBubble;
            gm.WS.Callbacks.OnNpcSocialAction -= HandleNpcSocialAction;
            gm.WS.Callbacks.OnNpcSocialContentResult -= HandleNpcSocialContentResult;
            gm.OnDialogueStarted -= HandlePlayerDialogueStarted;
            gm.OnDialogueEnded -= HandlePlayerDialogueEnded;
        }
        if (_socialCandidateController != null)
            _socialCandidateController.AcceptedDecision -= HandleAcceptedSocialDecision;
    }

    // ── 气泡处理 ──

    void HandleNpcBubble(NpcBubbleMsg msg)
    {
        if (_npcSpawner == null) return;

        var gm = GameManager.Instance;
        if (gm != null
            && gm.IsDialogueActive
            && (gm.CurrentDialogueNpcId == msg.npc_id || gm.CurrentDialogueNpcId == msg.target_npc_id))
        {
            return;
        }

        var npc = _npcSpawner.GetNpc(msg.npc_id);
        if (npc == null)
        {
            Debug.LogWarning($"[BubbleMgr] NPC 未找到: {msg.npc_id}");
            return;
        }

        if (!string.IsNullOrEmpty(msg.request_id) && !_socialProtocolController.IsPrepared(msg.request_id))
        {
            Debug.LogWarning($"[BubbleMgr] 忽略未准备或已取消的社交气泡: request={msg.request_id}");
            return;
        }

        string conversationKey = !string.IsNullOrEmpty(msg.request_id)
            ? msg.request_id
            : BuildConversationKey(msg.npc_id, msg.target_npc_id);
        _conversationParticipants[conversationKey] = new[] { msg.npc_id, msg.target_npc_id };

        // 加入队列
        if (!_queues.ContainsKey(conversationKey))
            _queues[conversationKey] = new Queue<BubbleEntry>();

        _queues[conversationKey].Enqueue(new BubbleEntry
        {
            speakerNpcId = msg.npc_id,
            text = msg.text,
            durationSec = msg.duration_sec,
            targetNpcId = msg.target_npc_id,
            conversationKey = conversationKey,
            waitStartedAt = Time.time,
            requestId = msg.request_id,
            lineIndex = msg.line_index,
            lineCount = msg.line_count,
        });

        // 如果没在显示，立即显示
        if (!_isShowing.GetValueOrDefault(conversationKey, false))
            ShowNext(conversationKey);
    }

    void ShowNext(string conversationKey)
    {
        if (!_queues.ContainsKey(conversationKey) || _queues[conversationKey].Count == 0)
        {
            _isShowing[conversationKey] = false;
            _rendezvousController.ReleaseConversationLock(conversationKey);
            return;
        }

        var entry = _queues[conversationKey].Dequeue();
        var npc = _npcSpawner.GetNpc(entry.speakerNpcId);
        if (npc == null)
        {
            _isShowing[conversationKey] = false;
            _rendezvousController.ReleaseConversationLock(conversationKey);
            return;
        }

        if (string.IsNullOrEmpty(entry.requestId)
            && _rendezvousController.ShouldWaitForParticipants(entry.speakerNpcId, entry.targetNpcId))
        {
            _isShowing[conversationKey] = true;
            StartCoroutine(WaitForParticipantsThenShow(entry));
            return;
        }

        DisplayBubbleEntry(entry);
    }

    /// <summary>
    /// 显示一条已经满足物理距离条件的世界气泡，并安排下一句。
    /// </summary>
    void DisplayBubbleEntry(BubbleEntry entry)
    {
        var npc = _npcSpawner.GetNpc(entry.speakerNpcId);
        if (npc == null)
        {
            _isShowing[entry.conversationKey] = false;
            _rendezvousController.ReleaseConversationLock(entry.conversationKey);
            return;
        }

        _rendezvousController.LockConversationParticipants(entry.conversationKey, entry.speakerNpcId, entry.targetNpcId);
        HideConversationBubbles(entry.speakerNpcId, entry.targetNpcId);
        _isShowing[entry.conversationKey] = true;
        npc.ShowBubble(entry.text, entry.durationSec);

        // 定时显示下一条——按对话双方轮流推进，而不是按单个 NPC 各播各的
        float delay = Mathf.Max(0.1f, entry.durationSec + _turnTransitionBufferSec);
        if (!string.IsNullOrEmpty(entry.requestId)
            && entry.lineCount > 0
            && entry.lineIndex >= entry.lineCount - 1)
        {
            StartCoroutine(CompleteProtocolConversationAfterDelay(entry, delay));
        }
        else
        {
            StartCoroutine(QueueNextRoutine(entry.conversationKey, delay));
        }
    }

    /// <summary>
    /// 等待 NPC 双方实际靠近后再显示气泡，避免隔着地图或店铺虚空交流。
    /// </summary>
    private System.Collections.IEnumerator WaitForParticipantsThenShow(BubbleEntry entry)
    {
        while (_rendezvousController.ShouldWaitForParticipants(entry.speakerNpcId, entry.targetNpcId))
        {
            if (Time.time - entry.waitStartedAt >= _rendezvousController.WaitTimeoutSec)
            {
                Debug.LogWarning($"[BubbleMgr] NPC 对话等待靠近超时，跳过气泡: {entry.speakerNpcId} → {entry.targetNpcId}");
                _isShowing[entry.conversationKey] = false;
                _rendezvousController.ReleaseConversationLock(entry.conversationKey);
                ShowNext(entry.conversationKey);
                yield break;
            }

            yield return new WaitForSeconds(_rendezvousController.RetryIntervalSec);
        }

        DisplayBubbleEntry(entry);
    }

    private System.Collections.IEnumerator QueueNextRoutine(string conversationKey, float delay)
    {
        yield return new WaitForSeconds(delay);
        ShowNext(conversationKey);
    }

    /// <summary>
    /// 最后一句显示结束后回报社交 COMPLETE，并释放双方移动锁。
    /// </summary>
    private System.Collections.IEnumerator CompleteProtocolConversationAfterDelay(BubbleEntry entry, float delay)
    {
        yield return new WaitForSeconds(delay);
        HideConversationBubbles(entry.speakerNpcId, entry.targetNpcId);
        _isShowing[entry.conversationKey] = false;
        _queues.Remove(entry.conversationKey);
        _conversationParticipants.Remove(entry.conversationKey);
        _rendezvousController.ReleaseConversationLock(entry.conversationKey);
        _socialProtocolController.CompletePlayback(
            entry.requestId,
            entry.speakerNpcId,
            entry.targetNpcId);
    }

    // ── 社交动作处理 ──

    void HandleNpcSocialAction(NpcSocialActionMsg msg)
    {
        if (_npcSpawner == null) return;

        HideConversationBubbles(msg.npc_id, msg.target_npc_id);
        _rendezvousController.ApplySocialAction(msg);
    }

    /// <summary>
    /// 语义 decision 通过候选重新校验后，由 Unity 原子 reservation 并启动会合。
    /// </summary>
    bool HandleAcceptedSocialDecision(NpcSocialDecisionResultMsg msg, string locationId)
    {
        if (_npcSpawner == null) return false;
        var gm = GameManager.Instance;
        if (gm != null
            && gm.IsDialogueActive
            && (gm.CurrentDialogueNpcId == msg.npc_id || gm.CurrentDialogueNpcId == msg.target_npc_id))
        {
            gm.SendNpcSocialFailed(
                msg.request_id,
                msg.npc_id,
                msg.target_npc_id,
                locationId,
                "player_dialogue_active");
            return false;
        }
        HideConversationBubbles(msg.npc_id, msg.target_npc_id);
        return _socialProtocolController.Begin(msg, locationId);
    }

    /// <summary>
    /// 接收纯内容结果并转换为本地气泡队列；迟到或 revision 不符时直接丢弃。
    /// </summary>
    void HandleNpcSocialContentResult(NpcSocialContentResultMsg msg)
    {
        if (!_socialProtocolController.TryAcceptContent(msg))
            return;
        int lineCount = msg.lines.Count;
        for (int index = 0; index < lineCount; index++)
        {
            NpcSocialContentLineMsg line = msg.lines[index];
            HandleNpcBubble(new NpcBubbleMsg
            {
                type = "NPC_BUBBLE",
                request_id = msg.request_id,
                npc_id = line.speaker_npc_id,
                target_npc_id = line.target_npc_id,
                text = line.text,
                duration_sec = line.duration_sec,
                style = "speech",
                line_index = index,
                line_count = lineCount,
            });
        }
    }

    /// <summary>
    /// 玩家与 NPC 打开正式对话时，清掉该 NPC 相关的世界空间气泡和排队内容。
    /// </summary>
    void HandlePlayerDialogueStarted(string npcId)
    {
        if (string.IsNullOrEmpty(npcId)) return;
        _socialProtocolController.CancelForNpc(npcId, "player_dialogue_interrupted");
        ClearConversationsForNpc(npcId);

        var npc = _npcSpawner.GetNpc(npcId);
        if (npc != null)
            npc.PushMotionLock(BuildPlayerDialogueLockReason(npcId));
    }

    /// <summary>
    /// 玩家正式对话结束时释放被对话 NPC 的移动锁。
    /// </summary>
    void HandlePlayerDialogueEnded(string npcId)
    {
        if (string.IsNullOrEmpty(npcId)) return;

        var npc = _npcSpawner.GetNpc(npcId);
        if (npc != null)
            npc.PopMotionLock(BuildPlayerDialogueLockReason(npcId));
    }

    /// <summary>
    /// 构造稳定的双人对话 key，让 A→B 和 B→A 进入同一队列。
    /// </summary>
    string BuildConversationKey(string npcId, string targetNpcId)
    {
        if (string.IsNullOrEmpty(targetNpcId))
            return npcId ?? string.Empty;

        return string.CompareOrdinal(npcId, targetNpcId) <= 0
            ? $"{npcId}|{targetNpcId}"
            : $"{targetNpcId}|{npcId}";
    }

    /// <summary>
    /// 显示当前发言前，先隐藏这组对话双方的旧气泡。
    /// </summary>
    void HideConversationBubbles(string npcId, string targetNpcId)
    {
        var npc = _npcSpawner.GetNpc(npcId);
        if (npc != null)
            npc.HideBubble();

        if (!string.IsNullOrEmpty(targetNpcId))
        {
            var targetNpc = _npcSpawner.GetNpc(targetNpcId);
            if (targetNpc != null)
                targetNpc.HideBubble();
        }
    }

    /// <summary>
    /// 清理某个 NPC 参与的所有对话队列，避免正式对话期间继续冒出旧气泡。
    /// </summary>
    void ClearConversationsForNpc(string npcId)
    {
        var keysToClear = new List<string>();
        foreach (var pair in _queues)
        {
            if (ConversationContainsNpc(pair.Key, npcId))
                keysToClear.Add(pair.Key);
        }

        foreach (var key in keysToClear)
        {
            ClearConversation(key, notifyBackend: true, reason: "player_dialogue_interrupted");
        }

        var npc = _npcSpawner.GetNpc(npcId);
        if (npc != null)
            npc.HideBubble();
    }

    /// <summary>
    /// 判断给定对话 key 是否包含指定 NPC。
    /// </summary>
    bool ConversationContainsNpc(string conversationKey, string npcId)
    {
        if (string.IsNullOrEmpty(conversationKey) || string.IsNullOrEmpty(npcId))
            return false;

        var ids = _conversationParticipants.TryGetValue(conversationKey, out var participants)
            ? participants
            : conversationKey.Split('|');
        foreach (var id in ids)
        {
            if (id == npcId)
                return true;
        }
        return false;
    }

    /// <summary>
    /// 通过对话 key 隐藏这组参与者的气泡。
    /// </summary>
    void HideConversationBubblesByKey(string conversationKey)
    {
        if (string.IsNullOrEmpty(conversationKey)) return;

        var ids = _conversationParticipants.TryGetValue(conversationKey, out var participants)
            ? participants
            : conversationKey.Split('|');
        if (ids.Length >= 1)
            HideConversationBubbles(ids[0], ids.Length >= 2 ? ids[1] : string.Empty);
    }

    /// <summary>
    /// 清理一组气泡；新协议会话可同时向后端回报播放失败。
    /// </summary>
    private void ClearConversation(string conversationKey, bool notifyBackend, string reason)
    {
        if (string.IsNullOrEmpty(conversationKey)) return;
        string[] participants = _conversationParticipants.TryGetValue(conversationKey, out var ids)
            ? ids
            : conversationKey.Split('|');
        if (_queues.TryGetValue(conversationKey, out var queue))
            queue.Clear();
        _queues.Remove(conversationKey);
        _isShowing[conversationKey] = false;
        _rendezvousController.ReleaseConversationLock(conversationKey);
        HideConversationBubblesByKey(conversationKey);
        if (notifyBackend && participants.Length >= 2 && _socialProtocolController.IsPrepared(conversationKey))
        {
            _socialProtocolController.FailPlayback(
                conversationKey,
                participants[0],
                participants[1],
                reason);
        }
        _conversationParticipants.Remove(conversationKey);
    }

    /// <summary>
    /// 构造玩家正式对话移动锁 reason。
    /// </summary>
    string BuildPlayerDialogueLockReason(string npcId)
    {
        return $"player_dialogue:{npcId}";
    }
}
