using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using TMPro;

/// <summary>
/// NPC 实体组件 — 挂载在每个 NPC GameObject 上。
/// 负责：移动（委托给 IMovementProvider）、动作可视化、气泡显示。
///
/// 预制体结构（用户填充 [SerializeField] 槽位）:
///   NpcPrefab (root, 挂 NpcEntity)
///   ├── Sprite (SpriteRenderer, 彩色占位方块)
///   ├── NameLabel (TextMeshPro, NPC 名字)
///   └── BubbleCanvas (Canvas, 挂 BubbleUI)
/// </summary>
public class NpcEntity : MonoBehaviour
{
    [Header("Identity")]
    public string NpcId;
    public string NpcName;

    [Header("Visual — 填充预制体引用")]
    [SerializeField] private SpriteRenderer _spriteRenderer;
    [SerializeField] private TMP_Text _nameLabel;
    [SerializeField] private BubbleUI _bubbleUI;

    [Header("Movement")]
    [SerializeField] private float _moveSpeed = 3.0f;

    [Header("Action Colors")]
    [SerializeField] private Color _colorDefault = Color.white;
    [SerializeField] private Color _colorTalk = new Color(1f, 0.9f, 0.5f);    // 淡黄
    [SerializeField] private Color _colorGiveItem = new Color(0.7f, 1f, 0.7f);  // 淡绿
    [SerializeField] private Color _colorWork = new Color(0.8f, 0.8f, 1f);      // 淡蓝

    public string CurrentLocation { get; private set; }
    public string CurrentAction { get; private set; }
    public bool IsMoving => _isMoving;

    private IMovementProvider _movement;
    private bool _isMoving;
    private Coroutine _moveRoutine;
    private readonly HashSet<string> _motionLocks = new();
    private string _pendingMoveLocationId;
    private Action<MovementResult> _pendingMoveOnArrived;
    private bool _ambientActive;
    private Coroutine _ambientRoutine;
    private string _ambientActionId;
    private string _ambientLabel;
    private int _ambientToken;

    public bool IsMotionLocked => _motionLocks.Count > 0;
    public bool IsAmbientActive => _ambientActive;
    public bool IsAmbientSlotAvailable =>
        !_ambientActive
        && !_isMoving
        && !IsMotionLocked
        && !IsShowingBubble
        && !string.IsNullOrEmpty(CurrentLocation)
        && IsAmbientBaseAction(CurrentAction);

    // ── 初始化 ──

    /// <summary>
    /// 初始化 NPC（由 NpcSpawner 创建后调用）。
    /// </summary>
    public void Initialize(string npcId, string npcName, IMovementProvider movementProvider = null)
    {
        NpcId = npcId;
        NpcName = npcName;
        _movement = movementProvider ?? new LerpMovementProvider();

        RefreshNameLabel();

        if (_spriteRenderer != null)
            _spriteRenderer.color = _colorDefault;

        gameObject.name = $"npc_{ToPurposeTag(npcId)}_dy";
    }

    // ── 移动 ──

    /// <summary>
    /// 移动到指定 location_id，自动查 LocationDatabase。
    /// 带随机偏移避免 NPC 堆叠。
    /// </summary>
    public void MoveToLocation(string locationId, Action<MovementResult> onArrived = null)
    {
        MoveToLocation(locationId, "walk", onArrived);
    }

    /// <summary>
    /// 按任务声明的 walk/run 模式移动到指定位置。
    /// </summary>
    public void MoveToLocation(
        string locationId,
        string movementMode,
        Action<MovementResult> onArrived = null)
    {
        if (IsMotionLocked)
        {
            _pendingMoveLocationId = locationId;
            _pendingMoveOnArrived = onArrived;
            Debug.Log($"[NpcEntity:{NpcId}] 移动锁定中，暂存移动目标: {locationId}");
            return;
        }

        if (_movement == null)
        {
            Debug.LogWarning($"[NpcEntity:{NpcId}] 移动提供者未初始化");
            onArrived?.Invoke(MovementResult.Failed);
            return;
        }

        if (!LocationDatabase.HasPosition(locationId))
        {
            Debug.LogWarning($"[NpcEntity:{NpcId}] 无坐标: {locationId}，跳过移动");
            onArrived?.Invoke(MovementResult.Failed);
            return;
        }

        _movement.Stop(transform);
        _isMoving = true;
        float resolvedSpeed = movementMode == "run" ? _moveSpeed * 1.75f : _moveSpeed;
        _movement.MoveToLocation(transform, locationId, resolvedSpeed, result =>
        {
            _isMoving = false;
            if (result == MovementResult.Succeeded)
                CurrentLocation = locationId;

            onArrived?.Invoke(result);
        });
    }

    /// <summary>
    /// 立即传送到指定位置（无动画）。
    /// </summary>
    public void TeleportTo(string locationId)
    {
        CancelAmbientPresentation();

        var pos = LocationDatabase.GetPosition(locationId);
        if (pos != null)
        {
            transform.position = new Vector3(pos.Value.x, pos.Value.y, transform.position.z);
            CurrentLocation = locationId;
        }
    }

    /// <summary>
    /// 给 NPC 增加移动锁；用于玩家正式对话或 NPC 头顶气泡对话期间冻结人物。
    /// </summary>
    public void PushMotionLock(string reason)
    {
        if (string.IsNullOrEmpty(reason))
            reason = "unknown";

        CancelAmbientPresentation();
        _motionLocks.Add(reason);
    }

    /// <summary>
    /// 移除移动锁；所有锁释放后执行最后一次暂存移动。
    /// </summary>
    public void PopMotionLock(string reason)
    {
        if (string.IsNullOrEmpty(reason))
            reason = "unknown";

        _motionLocks.Remove(reason);
        if (!IsMotionLocked)
            FlushPendingMove();
    }

    /// <summary>
    /// 解锁后只执行最后一次暂存移动，避免对话期间积压路径逐段乱跑。
    /// </summary>
    private void FlushPendingMove()
    {
        if (string.IsNullOrEmpty(_pendingMoveLocationId))
            return;

        string nextLocation = _pendingMoveLocationId;
        Action<MovementResult> nextCallback = _pendingMoveOnArrived;
        _pendingMoveLocationId = null;
        _pendingMoveOnArrived = null;

        MoveToLocation(nextLocation, nextCallback);
    }

    // ── 动作可视化（占位 — 改色表示状态）──

    /// <summary>
    /// 播放动作的视觉反馈。当前用颜色表示。
    /// 后续可替换为动画 / 粒子效果。
    /// </summary>
    public void PlayAction(string actionId)
    {
        CancelAmbientPresentation();

        CurrentAction = actionId;
        RefreshNameLabel();
        ApplyActionColor(actionId);
    }

    /// <summary>
    /// 尝试占用空闲表现槽播放原地小动作，不改变后端权威行为。
    /// </summary>
    public bool TryPlayAmbientPose(string actionId, string label, float durationSec)
    {
        if (!IsAmbientSlotAvailable)
            return false;

        int token = BeginAmbientPresentation(actionId, label);
        _ambientRoutine = StartCoroutine(EndAmbientAfterDelay(token, Mathf.Max(0.1f, durationSec)));
        return true;
    }

    /// <summary>
    /// 尝试占用空闲表现槽在当前 location 内踱步，移动路径仍走现有导航入口。
    /// </summary>
    public bool TryPlayAmbientPace(string actionId, string label)
    {
        if (!IsAmbientSlotAvailable)
            return false;

        int token = BeginAmbientPresentation(actionId, label);
        MoveToLocation(CurrentLocation, _ => ClearAmbientIfCurrent(token));
        return true;
    }

    /// <summary>
    /// 取消当前空闲表现；后端行为、对话锁或社交锁抢占空闲槽时调用。
    /// </summary>
    public void CancelAmbientPresentation()
    {
        if (!_ambientActive)
            return;

        _ambientToken++;
        if (_ambientRoutine != null)
        {
            StopCoroutine(_ambientRoutine);
            _ambientRoutine = null;
        }

        _ambientActive = false;
        _ambientActionId = null;
        _ambientLabel = null;
        RefreshNameLabel();
        ApplyActionColor(CurrentAction);

        if (_isMoving && _movement != null)
        {
            _movement.Stop(transform);
            _isMoving = false;
        }
    }

    /// <summary>
    /// 捕获玩家当前看到的 NPC 视觉上下文，可选地同时打断空闲表现。
    /// </summary>
    public NpcVisualContext CaptureVisualContext(bool interruptAmbient)
    {
        bool ambientWasActive = _ambientActive;
        var context = new NpcVisualContext
        {
            base_action_id = string.IsNullOrEmpty(CurrentAction) ? "stand" : CurrentAction,
            ambient_action_id = ambientWasActive ? _ambientActionId : string.Empty,
            ambient_label = ambientWasActive ? _ambientLabel : string.Empty,
            location_id = CurrentLocation,
            is_interrupting_ambient = ambientWasActive && interruptAmbient,
        };

        if (interruptAmbient)
            CancelAmbientPresentation();

        return context;
    }

    /// <summary>
    /// 按“名字 + 当前行为后缀”刷新名字牌显示。
    /// </summary>
    private void RefreshNameLabel()
    {
        if (_nameLabel == null) return;

        var displayName = string.IsNullOrEmpty(NpcName) ? NpcId : NpcName;
        var suffix = _ambientActive && !string.IsNullOrEmpty(_ambientLabel)
            ? $"（{_ambientLabel}）"
            : GetActionStatusSuffix(CurrentAction);
        _nameLabel.text = string.IsNullOrEmpty(suffix) ? displayName : $"{displayName}{suffix}";
    }

    /// <summary>
    /// 应用动作对应的占位颜色。
    /// </summary>
    private void ApplyActionColor(string actionId)
    {
        if (_spriteRenderer == null) return;

        switch (actionId)
        {
            case "talk":
            case "greet":
                _spriteRenderer.color = _colorTalk;
                break;
            case "give_item":
                _spriteRenderer.color = _colorGiveItem;
                break;
            case "work_open":
            case "work_close":
            case "stand":
                _spriteRenderer.color = _colorWork;
                break;
            default:
                _spriteRenderer.color = _colorDefault;
                break;
        }
    }

    /// <summary>
    /// 判断当前后端主行为是否允许被前端空闲表现临时占用。
    /// </summary>
    private static bool IsAmbientBaseAction(string actionId)
    {
        return string.IsNullOrEmpty(actionId) || actionId == "stand";
    }

    /// <summary>
    /// 开始一次空闲表现并刷新前端显示。
    /// </summary>
    private int BeginAmbientPresentation(string actionId, string label)
    {
        _ambientToken++;
        _ambientActive = true;
        _ambientActionId = string.IsNullOrEmpty(actionId) ? "ambient_idle" : actionId;
        _ambientLabel = string.IsNullOrEmpty(label) ? "待着" : label;
        RefreshNameLabel();
        return _ambientToken;
    }

    /// <summary>
    /// 延迟结束当前 token 对应的空闲表现。
    /// </summary>
    private IEnumerator EndAmbientAfterDelay(int token, float durationSec)
    {
        yield return new WaitForSeconds(durationSec);
        ClearAmbientIfCurrent(token);
    }

    /// <summary>
    /// 仅当 token 仍匹配时释放空闲表现槽。
    /// </summary>
    private void ClearAmbientIfCurrent(int token)
    {
        if (!_ambientActive || token != _ambientToken)
            return;

        _ambientActive = false;
        _ambientRoutine = null;
        _ambientActionId = null;
        _ambientLabel = null;
        RefreshNameLabel();
        ApplyActionColor(CurrentAction);
    }

    /// <summary>
    /// 将后端 action_id 转成玩家可读的状态后缀。
    /// </summary>
    private static string GetActionStatusSuffix(string actionId)
    {
        if (string.IsNullOrEmpty(actionId)) return string.Empty;

        if (actionId.StartsWith("work_", StringComparison.Ordinal))
            return "（工作中）";

        if (actionId.StartsWith("react_", StringComparison.Ordinal))
            return "（反应中）";

        if (actionId.StartsWith("special_", StringComparison.Ordinal))
            return "（忙碌中）";

        return actionId switch
        {
            "patrol" => "（巡逻中）",
            "visit" => "（拜访中）",
            "sleep" => "（睡觉中）",
            "stand" => "（待机中）",
            "sit" or "lean" or "rest" => "（休息中）",
            "read" => "（阅读中）",
            "eat" => "（用餐中）",
            "drink" => "（喝东西）",
            "stare_outside" or "browse" => "（发呆中）",
            "feed_cats" => "（喂猫中）",
            "greet" or "talk" => "（交流中）",
            "give_item" => "（送东西中）",
            "observe" => "（观察中）",
            _ => "（行动中）",
        };
    }

    // ── 气泡 ──

    /// <summary>
    /// 显示对话气泡。委托给 BubbleUI 子组件。
    /// </summary>
    public void ShowBubble(string text, float durationSec)
    {
        if (_bubbleUI != null)
            _bubbleUI.Show(text, durationSec);
        else
            Debug.Log($"[气泡:{NpcName}] {text}");
    }

    /// <summary>
    /// 隐藏气泡。
    /// </summary>
    public void HideBubble()
    {
        if (_bubbleUI != null)
            _bubbleUI.Hide();
    }

    /// <summary>
    /// 是否正在显示气泡。
    /// </summary>
    public bool IsShowingBubble => _bubbleUI != null && _bubbleUI.IsShowing;

    // ── 颜色配置（外部可设）──

    public void SetColors(Color defaultCol, Color talkCol, Color giveCol, Color workCol)
    {
        _colorDefault = defaultCol;
        _colorTalk = talkCol;
        _colorGiveItem = giveCol;
        _colorWork = workCol;
        if (_spriteRenderer != null)
            _spriteRenderer.color = _colorDefault;
    }

    public void SetMoveSpeed(float speed)
    {
        _moveSpeed = speed;
    }

    /// <summary>
    /// 将共享 ID 转成 GameObject 命名中的 purposeTag。
    /// </summary>
    private static string ToPurposeTag(string value)
    {
        if (string.IsNullOrEmpty(value)) return "unknown";

        var parts = value.Split('_');
        for (int i = 1; i < parts.Length; i++)
        {
            if (string.IsNullOrEmpty(parts[i])) continue;
            parts[i] = char.ToUpperInvariant(parts[i][0]) + parts[i][1..];
        }

        return string.Concat(parts);
    }
}
