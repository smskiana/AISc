using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// NPC 生成器 — 管理 NPC GameObject 生命周期。
/// 挂载在场景空 GameObject 上。
///
/// 监听 GameManager 事件:
///   OnGameReady  → 创建所有 NPC
///
/// 预制体槽位（用户填充）:
///   每个 NPC 有独立预制体槽位（_npcSakura / _npcChihaya / ...）
///   如果不填，运行时会动态创建对应颜色的方块。
/// </summary>
public class NpcSpawner : MonoBehaviour
{
    [Header("预制体 — 不同人物")]
    [SerializeField] private GameObject _npcSakura;
    [SerializeField] private GameObject _npcChihaya;
    [SerializeField] private GameObject _npcKazuha;
    [SerializeField] private GameObject _npcTatsunosuke;
    [SerializeField] private GameObject _npcKujo;

    [Header("移动")]
    [SerializeField] private float _defaultMoveSpeed = 3.0f;
    [SerializeField] private bool _useAStarNavigation = true;
    [SerializeField] private NavigationGridAsset _navigationGrid;

    [Header("NPC 占位颜色")]
    [SerializeField] private Color _colorSakura = new Color(1f, 0.7f, 0.8f);       // 樱粉
    [SerializeField] private Color _colorChihaya = new Color(1f, 0.85f, 0.5f);     // 小麦色
    [SerializeField] private Color _colorKazuha = new Color(0.5f, 0.7f, 0.5f);     // 墨绿
    [SerializeField] private Color _colorTatsunosuke = new Color(0.7f, 0.5f, 0.8f); // 紫
    [SerializeField] private Color _colorKujo = new Color(0.4f, 0.5f, 0.6f);       // 灰蓝

    // NPC 名称映射
    private static readonly Dictionary<string, string> NPC_NAMES = new()
    {
        {"sakura", "鹿岛樱"},
        {"chihaya", "千早"},
        {"kazuha", "和叶"},
        {"tatsunosuke", "龙之介"},
        {"kujo", "九条莲"},
    };

    private Dictionary<string, NpcEntity> _npcs = new();
    private IMovementProvider _movementProvider;
    private NpcBehaviorApplier _behaviorApplier;
    private NpcAmbientBehaviorController _ambientBehaviorController;
    private readonly Dictionary<string, NpcDailyScheduleController> _dailySchedules = new();
    private readonly Dictionary<string, NpcRuntimeStateController> _runtimeStates = new();
    private readonly Dictionary<string, string> _scheduleCandidateByRequest = new();
    private NpcActionResultReporter _actionResultReporter;
    private NpcSocialCandidateController _socialCandidateController;

    // ── 初始化 ──

    /// <summary>
    /// 初始化 NPC 生成器，并按配置选择直线移动或 A* 寻路移动。
    /// </summary>
    void Start()
    {
        if (_useAStarNavigation && _navigationGrid != null)
        {
            _movementProvider = new AStarMovementProvider(_navigationGrid);
            Debug.Log("[NpcSpawner] 使用 A* 导航移动");
        }
        else
        {
            _movementProvider = new LerpMovementProvider();
            Debug.Log("[NpcSpawner] 使用直线移动");
        }
        _actionResultReporter = new NpcActionResultReporter(GameManager.Instance);
        _actionResultReporter.TerminalReported += HandleTaskTerminal;
        _behaviorApplier = new NpcBehaviorApplier(_actionResultReporter);
        _ambientBehaviorController = new NpcAmbientBehaviorController();
        _socialCandidateController = gameObject.GetComponent<NpcSocialCandidateController>();
        if (_socialCandidateController == null)
            _socialCandidateController = gameObject.AddComponent<NpcSocialCandidateController>();
        _socialCandidateController.Initialize(this);

        var gm = GameManager.Instance;
        if (gm != null)
        {
            gm.OnGameReady += HandleGameReady;
            gm.OnNpcDailyScheduleReady += HandleNpcDailyScheduleReady;
            gm.OnNpcStateEffect += HandleNpcStateEffect;
            gm.OnAuthoritativeGameTimeChanged += HandleAuthoritativeGameTimeChanged;
        }

        Debug.Log("[NpcSpawner] 就绪");
    }

    void OnDestroy()
    {
        var gm = GameManager.Instance;
        if (gm != null)
        {
            gm.OnGameReady -= HandleGameReady;
            gm.OnNpcDailyScheduleReady -= HandleNpcDailyScheduleReady;
            gm.OnNpcStateEffect -= HandleNpcStateEffect;
            gm.OnAuthoritativeGameTimeChanged -= HandleAuthoritativeGameTimeChanged;
        }
        if (_actionResultReporter != null)
            _actionResultReporter.TerminalReported -= HandleTaskTerminal;
    }

    // ── 公开 API ──

    /// <summary>
    /// 获取已生成的 NPC 实体。
    /// </summary>
    public NpcEntity GetNpc(string npcId)
    {
        _npcs.TryGetValue(npcId, out var entity);
        return entity;
    }

    /// <summary>
    /// 获取所有 NPC ID 列表。
    /// </summary>
    public IEnumerable<string> GetAllNpcIds() => _npcs.Keys;

    /// <summary>
    /// 获取所有已生成 NPC 实体，供前端表现层按游戏时间调度。
    /// </summary>
    public IEnumerable<NpcEntity> GetAllNpcs() => _npcs.Values;

    /// <summary>
    /// 返回当前正式 NPC 任务的只读诊断快照。
    /// </summary>
    public List<NpcTaskDiagnosticSnapshot> GetTaskDiagnosticSnapshots()
    {
        return _behaviorApplier?.GetTaskDiagnosticSnapshots() ?? new List<NpcTaskDiagnosticSnapshot>();
    }

    /// <summary>
    /// 睡眠开始时取消正式任务、空闲表现和移动，并锁定 NPC。
    /// </summary>
    public void PrepareForSleep()
    {
        _behaviorApplier?.CancelAll("day_ended");
        foreach (var npc in _npcs.Values)
        {
            _ambientBehaviorController?.CancelAmbient(npc);
            npc.PushMotionLock(PauseSources.SleepFlow);
        }
    }

    /// <summary>
    /// 次日醒来后释放 NPC 睡眠移动锁。
    /// </summary>
    public void ResumeAfterSleep()
    {
        foreach (var npc in _npcs.Values)
            npc.PopMotionLock(PauseSources.SleepFlow);
    }

    /// <summary>
    /// 捕获指定 NPC 当前视觉上下文，玩家搭话时附给后端。
    /// </summary>
    public NpcVisualContext CaptureVisualContext(string npcId, bool interruptAmbient)
    {
        return _ambientBehaviorController?.CaptureVisualContext(GetNpc(npcId), interruptAmbient);
    }

    // ── 事件处理 ──

    void HandleGameReady(GameReadyMsg msg)
    {
        Debug.Log($"[NpcSpawner] GameReady — 生成 {msg.npcs?.Count ?? 0} 个 NPC");

        if (msg.npcs != null)
        {
            foreach (var state in msg.npcs)
            {
                SpawnOrUpdateNpc(state);
            }
        }

        _ambientBehaviorController?.Prime(GetAllNpcs(), msg.game_time);
    }

    /// <summary>
    /// 幂等接收后端完整日计划，并由 Unity 保存剩余计划权威。
    /// </summary>
    void HandleNpcDailyScheduleReady(NpcDailyScheduleReadyMsg msg)
    {
        if (msg == null || string.IsNullOrWhiteSpace(msg.npc_id))
            return;
        if (!_dailySchedules.TryGetValue(msg.npc_id, out var controller))
        {
            controller = new NpcDailyScheduleController();
            _dailySchedules[msg.npc_id] = controller;
        }
        if (!controller.TryReplace(msg, out string reason))
        {
            Debug.LogWarning($"[NpcSchedule] 拒绝 {msg.npc_id} revision={msg.schedule_revision} reason={reason}");
            return;
        }
        Debug.Log($"[NpcSchedule] 接收 {msg.npc_id} day={msg.game_day} revision={msg.schedule_revision} items={msg.items?.Count ?? 0} reason={reason}");
    }

    /// <summary>
    /// 返回所有 NPC 日程控制器，供存档与诊断读取。
    /// </summary>
    public IReadOnlyDictionary<string, NpcDailyScheduleController> GetDailySchedules()
    {
        return _dailySchedules;
    }

    /// <summary>
    /// 查询单名 NPC 的 Unity 权威日程控制器。
    /// </summary>
    public bool TryGetDailySchedule(string npcId, out NpcDailyScheduleController schedule)
    {
        return _dailySchedules.TryGetValue(npcId, out schedule);
    }

    /// <summary>
    /// 导出 Unity 日程接收、pending 和最近裁决的只读诊断快照。
    /// </summary>
    public List<NpcDailyScheduleDiagnosticSnapshot> GetDailyScheduleDiagnosticSnapshots()
    {
        var snapshots = new List<NpcDailyScheduleDiagnosticSnapshot>();
        foreach (var pair in _dailySchedules)
        {
            NpcDailyScheduleController schedule = pair.Value;
            snapshots.Add(new NpcDailyScheduleDiagnosticSnapshot
            {
                npc_id = pair.Key,
                schedule_day = schedule.ScheduleDay,
                schedule_revision = schedule.ScheduleRevision,
                planner_version = schedule.PlannerVersion,
                remaining_count = schedule.Remaining.Count,
                pending_candidate_id = schedule.PendingCandidate?.candidate_id ?? string.Empty,
                last_decision_reason = schedule.LastDecisionReason,
                payload_fingerprint = schedule.AcceptedPayloadFingerprint,
                last_operation_id = schedule.LastOperationId,
            });
        }
        return snapshots;
    }

    /// <summary>
    /// 导出 Unity 权威运行时状态的诊断快照。
    /// </summary>
    public List<NpcRuntimeStateDiagnosticSnapshot> GetRuntimeStateDiagnosticSnapshots()
    {
        var snapshots = new List<NpcRuntimeStateDiagnosticSnapshot>();
        foreach (var pair in _runtimeStates)
        {
            NpcRuntimeStateController state = pair.Value;
            snapshots.Add(new NpcRuntimeStateDiagnosticSnapshot
            {
                npc_id = pair.Key,
                emotion = state.Emotion,
                energy = state.Energy,
                sociability = state.Sociability,
                current_need = state.CurrentNeed,
                is_asleep = state.IsAsleep,
                lingering_concern = state.LingeringConcern,
                last_effect_operation_id = state.LastEffectOperationId,
                last_effect_status = state.LastEffectStatus,
                last_effect_reason = state.LastEffectReason,
            });
        }
        return snapshots;
    }

    /// <summary>
    /// 把仅剩余、未终态消费的日程写入 Unity 主存档字段。
    /// </summary>
    public void WriteDailySchedulesToSave(List<NpcWorldSaveData> savedNpcs)
    {
        if (savedNpcs == null)
            return;
        foreach (NpcWorldSaveData savedNpc in savedNpcs)
        {
            if (savedNpc == null || !_dailySchedules.TryGetValue(savedNpc.npc_id, out var schedule))
                continue;
            savedNpc.schedule_day = schedule.ScheduleDay;
            savedNpc.schedule_revision = schedule.ScheduleRevision;
            savedNpc.schedule_planner_version = schedule.PlannerVersion;
            savedNpc.remaining_daily_schedule = schedule.ExportRemaining();
            if (_runtimeStates.TryGetValue(savedNpc.npc_id, out var runtime))
            {
                savedNpc.current_need = runtime.CurrentNeed;
                savedNpc.is_asleep = runtime.IsAsleep;
                savedNpc.lingering_concern = runtime.LingeringConcern;
            }
        }
    }

    /// <summary>
    /// 从 Unity 主存档恢复当日剩余日程；不同游戏日的旧计划必须由后端重新准备。
    /// </summary>
    public void RestoreDailySchedulesFromSave(GameSaveData data)
    {
        if (data?.game_time == null)
            return;
        _dailySchedules.Clear();
        _scheduleCandidateByRequest.Clear();
        foreach (NpcWorldSaveData savedNpc in data.npcs ?? new List<NpcWorldSaveData>())
        {
            if (savedNpc == null || savedNpc.schedule_day != data.game_time.day)
                continue;
            var controller = new NpcDailyScheduleController();
            controller.Restore(
                savedNpc.schedule_day,
                savedNpc.schedule_revision,
                savedNpc.schedule_planner_version,
                savedNpc.remaining_daily_schedule);
            _dailySchedules[savedNpc.npc_id] = controller;
        }
    }

    /// <summary>
    /// 每个 Unity 权威游戏分钟评估所有 NPC 的下一日程候选。
    /// </summary>
    private void HandleAuthoritativeGameTimeChanged(GameTime gameTime)
    {
        if (gameTime == null)
            return;
        foreach (var pair in _dailySchedules)
        {
            if (pair.Value.ScheduleDay > 0 && pair.Value.ScheduleDay != gameTime.day)
                pair.Value.ClearForNewDay();
        }
        foreach (var pair in _dailySchedules)
        {
            NpcEntity npc = GetNpc(pair.Key);
            if (npc == null)
                continue;
            bool isRuntimeReserved = npc.IsMotionLocked || (_socialCandidateController?.IsReserved(pair.Key) ?? false);
            NpcScheduleSwitchResult decision = pair.Value.EvaluateNext(gameTime.hour, gameTime.minute, isRuntimeReserved);
            if (decision.Decision == NpcScheduleSwitchDecision.Switch)
                StartScheduleCandidate(pair.Key, pair.Value, npc);
            else if (decision.Decision == NpcScheduleSwitchDecision.SkipNext && pair.Value.PendingCandidate != null)
                pair.Value.Consume(pair.Value.PendingCandidate.candidate_id);
            else if (decision.Decision == NpcScheduleSwitchDecision.RequestReplan)
                RequestScheduleReplan(pair.Key, pair.Value, "schedule_window_expired", decision.Reason);
        }
        foreach (var pair in _runtimeStates)
        {
            NpcEntity npc = GetNpc(pair.Key);
            pair.Value.Tick(gameTime, npc?.CurrentAction);
            var storeState = GameManager.Instance?.NPCs?.Find(state => state.npc_id == pair.Key);
            pair.Value.CopyTo(storeState);
        }
    }

    /// <summary>
    /// 将已裁决候选转换为现有统一任务执行器输入。
    /// </summary>
    private void StartScheduleCandidate(string npcId, NpcDailyScheduleController controller, NpcEntity npc)
    {
        NpcDailyScheduleItem candidate = controller.PendingCandidate;
        if (candidate == null)
            return;
        if (_socialCandidateController?.IsReserved(npcId) ?? false)
            return;
        string requestId = $"schedule:{controller.ScheduleDay}:{controller.ScheduleRevision}:{candidate.candidate_id}";
        if (_scheduleCandidateByRequest.ContainsKey(requestId))
            return;
        _scheduleCandidateByRequest[requestId] = candidate.candidate_id;
        _ambientBehaviorController?.CancelAmbient(npc);
        _behaviorApplier.Apply(new NpcTaskCommand
        {
            request_id = requestId,
            npc_id = npcId,
            behavior = new NpcBehaviorCmd
            {
                action_id = candidate.action_id,
                location_id = candidate.location_id,
                expected_duration_sec = 1f,
                movement_mode = "walk",
                interruptible = true,
            },
            context = new BehaviorContext { reason = "daily_schedule", plan_source = candidate.source },
        }, npc);
    }

    /// <summary>
    /// 用 Unity 权威剩余计划请求后端重排单名 NPC 的后续日程。
    /// </summary>
    private void RequestScheduleReplan(string npcId, NpcDailyScheduleController controller, string interactionType, string reason)
    {
        var gm = GameManager.Instance;
        var state = gm?.NPCs?.Find(item => item.npc_id == npcId);
        if (gm == null || state == null)
            return;
        gm.SendNpcScheduleReplanRequest(
            $"schedule_replan:{npcId}:{controller.ScheduleRevision}:{System.Guid.NewGuid():N}",
            npcId,
            interactionType,
            reason,
            controller.LastDecisionReason,
            new[] { npcId },
            controller.ScheduleRevision,
            controller.ExportRemaining(),
            state);
    }

    /// <summary>
    /// 真实任务终态后消费对应候选；非日程任务不触碰剩余计划。
    /// </summary>
    private void HandleTaskTerminal(NpcTaskCommand message, string status, string reason)
    {
        if (message == null || !_scheduleCandidateByRequest.TryGetValue(message.request_id, out string candidateId))
            return;
        _scheduleCandidateByRequest.Remove(message.request_id);
        if (_dailySchedules.TryGetValue(message.npc_id, out var controller))
            controller.Consume(candidateId);
    }

    /// <summary>
    /// 应用 Python 计算但由 Unity 校验的 NPC 状态 effect。
    /// </summary>
    void HandleNpcStateEffect(NpcStateEffectMsg msg)
    {
        if (msg == null || string.IsNullOrWhiteSpace(msg.npc_id))
            return;
        if (!_runtimeStates.TryGetValue(msg.npc_id, out var controller))
            return;
        if (!controller.TryApplyEffect(msg, GameManager.Instance != null ? GameManager.Instance.WorldRevision : 0))
            return;
        var storeState = GameManager.Instance?.NPCs?.Find(state => state.npc_id == msg.npc_id);
        controller.CopyTo(storeState);
    }

    // ── NPC 生成 ──

    void SpawnOrUpdateNpc(NpcState state)
    {
        if (_npcs.TryGetValue(state.npc_id, out var existing))
        {
            // 更新位置
            if (!existing.IsMoving)
            {
                existing.TeleportTo(state.current_location);
                existing.PlayAction(state.current_action ?? "stand");
            }
            RestoreRuntimeState(state);
            return;
        }

        // 新建 NPC
        var go = CreateNpcGameObject(state.npc_id);
        var entity = go.GetComponent<NpcEntity>();
        if (entity == null)
            entity = go.AddComponent<NpcEntity>();

        var name = NPC_NAMES.GetValueOrDefault(state.npc_id, state.npc_id);
        var color = GetNpcColor(state.npc_id);
        entity.Initialize(state.npc_id, name, _movementProvider);
        entity.SetColors(color, color, Color.yellow, Color.cyan);
        entity.SetMoveSpeed(_defaultMoveSpeed);

        // 放置到起始位置
        entity.TeleportTo(state.current_location);
        entity.PlayAction(state.current_action ?? "stand");

        _npcs[state.npc_id] = entity;
        RestoreRuntimeState(state);
        Debug.Log($"[NpcSpawner] 生成 {state.npc_id} ({name}) @ {state.current_location}");
    }

    /// <summary>
    /// 从后端初始状态或 Unity 存档状态恢复 NPC 运行时状态模块。
    /// </summary>
    private void RestoreRuntimeState(NpcState state)
    {
        if (state == null || string.IsNullOrWhiteSpace(state.npc_id))
            return;
        if (!_runtimeStates.TryGetValue(state.npc_id, out var runtime))
        {
            runtime = new NpcRuntimeStateController();
            _runtimeStates[state.npc_id] = runtime;
        }
        runtime.Restore(state);
    }

    /// <summary>
    /// 根据 npcId 选择对应预制体，若无则创建占位方块。
    /// </summary>
    GameObject CreateNpcGameObject(string npcId)
    {
        var prefab = GetNpcPrefab(npcId);
        if (prefab != null)
        {
            var go = Instantiate(prefab, transform);
            go.name = BuildNpcRuntimeName(npcId);
            EnsureCollider(go);
            return go;
        }

        // 回退：动态创建方块 + 标签
        var fallback = new GameObject(BuildNpcRuntimeName(npcId));
        fallback.transform.SetParent(transform);

        // SpriteRenderer（彩色方块占位）
        var sr = fallback.AddComponent<SpriteRenderer>();
        sr.sprite = CreatePlaceholderSprite();
        sr.color = GetNpcColor(npcId);
        sr.sortingOrder = 5;

        EnsureCollider(fallback);
        return fallback;
    }

    /// <summary>
    /// 确保 GameObject 有碰撞体（用于鼠标点击检测）
    /// </summary>
    void EnsureCollider(GameObject go)
    {
        var col = go.GetComponent<Collider2D>();
        if (col == null)
        {
            var bc = go.AddComponent<BoxCollider2D>();
            bc.size = new Vector2(1.5f, 2.5f);
            bc.isTrigger = true;  // 不阻碍移动，只用于点击检测
        }
    }

    /// <summary>
    /// 根据 npcId 返回对应预制体引用。
    /// </summary>
    GameObject GetNpcPrefab(string npcId) => npcId switch
    {
        "sakura" => _npcSakura,
        "chihaya" => _npcChihaya,
        "kazuha" => _npcKazuha,
        "tatsunosuke" => _npcTatsunosuke,
        "kujo" => _npcKujo,
        _ => null,
    };

    // ── 辅助 ──

    Color GetNpcColor(string npcId) => npcId switch
    {
        "sakura" => _colorSakura,
        "chihaya" => _colorChihaya,
        "kazuha" => _colorKazuha,
        "tatsunosuke" => _colorTatsunosuke,
        "kujo" => _colorKujo,
        _ => Color.white,
    };

    /// <summary>
    /// 统一构造运行时 NPC 根节点名称，避免 Play 模式回退到旧命名。
    /// </summary>
    string BuildNpcRuntimeName(string npcId) => $"npc_{ToPurposeTag(npcId)}_dy";

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

    /// <summary>
    /// 创建 1×1 白色方块 Sprite（占位用）。
    /// </summary>
    Sprite CreatePlaceholderSprite()
    {
        var tex = new Texture2D(4, 4);
        var colors = new Color[16];
        for (int i = 0; i < 16; i++) colors[i] = Color.white;
        tex.SetPixels(colors);
        tex.filterMode = FilterMode.Point;
        tex.Apply();
        var rect = new Rect(0, 0, 4, 4);
        return Sprite.Create(tex, rect, new Vector2(0.5f, 0.5f), 4);
    }
}
