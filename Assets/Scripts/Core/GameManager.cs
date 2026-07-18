using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 游戏管理器 — 持有 WS 客户端 + 回调注册。
/// 挂在场景中的空 GameObject 上。
/// </summary>
public class GameManager : MonoBehaviour
{
    public static GameManager Instance { get; private set; }

    [Header("Server")]
    [SerializeField] private string _serverUrl = "http://127.0.0.1:8766";
    [Header("刷新")]
    [SerializeField] private bool needFlesh;
    [Header("启动")]
    [SerializeField] private bool _autoStartGameOnConnect = false;
    [SerializeField] private string _autoStartMode = "CONTINUE";

    [Header("对话 UI")]
    [SerializeField] private PortraitDialogueUI _dialogueUI;

    public WebSocketClient WS { get; private set; }
    public UnitySaveService SaveService => _saveService;
    public GameTime CurrentTime => _gameTimeController?.CurrentTime;
    public List<NpcState> NPCs => _stateStore.NPCs;
    public string PlayerLocation => _stateStore.PlayerLocation;
    public bool IsSleeping => _stateStore.IsSleeping;
    public bool IsDialogueActive => _stateStore.IsDialogueActive;
    public bool IsGameplayReady => _stateStore.IsGameplayReady;
    public string CurrentDialogueNpcId => _stateStore.CurrentDialogueNpcId;
    public long WorldRevision => _stateStore.WorldRevision;
    public WorldPreparationDiagnosticSnapshot WorldPreparationSnapshot { get; private set; } = new WorldPreparationDiagnosticSnapshot();

    private string _pendingLoadSlot;
    private string _pendingDialogueRequestId;
    private string _pendingDialogueLocation;
    private NpcVisualContext _pendingDialogueVisualContext;
    private readonly GameStateStore _stateStore = new GameStateStore();
    private GameCommandSender _commandSender;
    private UnitySaveService _saveService;
    private GameTimeController _gameTimeController;
    private InventoryController _inventoryController;

    // 事件
    public event Action<GameReadyMsg> OnGameReady;
    public event Action<LoadCompleteMsg> OnLoadComplete;
    public event Action<GameTime> OnAuthoritativeGameTimeChanged;
    public event Action<NpcDailyScheduleReadyMsg> OnNpcDailyScheduleReady;
    public event Action<NpcStateEffectMsg> OnNpcStateEffect;
    public event Action<DialogueTokenMsg> OnDialogueToken;
    public event Action<string> OnDialogueStarted;
    public event Action<string> OnDialogueEnded;
    public event Action<SaveCompleteMsg> OnSaveComplete;
    public event Action<SavesListMsg> OnSavesList;
    public event Action<GameErrorMsg> OnGameError;
    public event Action<string> OnPlayerLocationChanged;
    public event Action<MidnightSettlementCompleteMsg> OnMidnightSettlementComplete;
    public event Action<MidnightSettlementFailedMsg> OnMidnightSettlementFailed;
    public event Action<WorldPreparationProgressMsg> OnWorldPreparationProgress;

    void Awake()
    {
        if (Instance != null) { Destroy(gameObject); return; }
        Instance = this;
        DontDestroyOnLoad(gameObject);

        WS = GetComponent<WebSocketClient>();
        if (WS == null) WS = gameObject.AddComponent<WebSocketClient>();
        _gameTimeController = GetComponent<GameTimeController>();
        if (_gameTimeController != null)
            _gameTimeController.TimeChanged += HandleAuthoritativeGameTimeChanged;
        _inventoryController = GetComponent<InventoryController>();
        _commandSender = new GameCommandSender(WS);
        _saveService = new UnitySaveService(WS, _stateStore, () => CurrentTime, _inventoryController);
        _saveService.SaveFinished += HandleUnitySaveFinished;
        _saveService.LoadFinished += HandleUnityLoadFinished;

        // 注册回调
        WS.Callbacks = new Callbacks
        {
            OnGameReady = HandleGameReady,
            OnLoadComplete = HandleLoadComplete,
            OnNpcDailyScheduleReady = (msg) => OnNpcDailyScheduleReady?.Invoke(msg),
            OnNpcStateEffect = (msg) => OnNpcStateEffect?.Invoke(msg),
            OnNpcScheduleReplanContext = HandleNpcScheduleReplanContext,
            OnDialogueToken = (msg) => {
                OnDialogueToken?.Invoke(msg);
            },
            OnDialoguePrepared = HandleDialoguePrepared,
            OnDialogueComplete = (msg) => {
                Debug.Log($"[对话完成] {msg.npc_id}:\n{msg.npc_text_complete}");
                if (_dialogueUI != null)
                    _dialogueUI.OnNpcReplyComplete(msg.npc_text_complete, msg.choices);
            },
            OnDialogueChoicesUpdate = (msg) => {
                Debug.Log($"[对话选项更新] {msg.npc_id}: {msg.choices?.Count ?? 0}");
                if (_dialogueUI != null && IsDialogueActive && CurrentDialogueNpcId == msg.npc_id)
                    _dialogueUI.UpdateSuggestionChoices(msg.choices);
            },
            OnDialogueClose = (msg) => {
                Debug.Log($"[对话结束] {msg.npc_id} reason={msg.reason}");
                CloseDialogueLocal(msg.npc_id);
            },
            OnSaveComplete = (msg) => {
                Debug.Log($"[存档完成] slot={msg.slot} success={msg.success}");
                OnSaveComplete?.Invoke(msg);
            },
            OnSavesList = (msg) => {
                Debug.Log($"[存档列表] {msg.saves?.Count ?? 0} 项");
                OnSavesList?.Invoke(msg);
            },
            OnNpcBubble = (msg) => Debug.Log($"[气泡] {msg.npc_id}: {msg.text}"),
            OnNpcSocialAction = (msg) => Debug.Log($"[社交] {msg.npc_id} → {msg.target_npc_id} [{msg.action_id}]"),
            OnNpcSocialAck = (msg) => {
                if (!msg.accepted)
                    Debug.LogWarning($"[NPC社交] 后端拒绝 request={msg.request_id} reason={msg.reason}");
            },
            OnGameError = (msg) => {
                Debug.LogError($"[服务器错误] {msg.message}");
                WorldPreparationSnapshot.failure_reason = msg.message ?? string.Empty;
                WorldPreparationSnapshot.is_active = false;
                OnGameError?.Invoke(msg);
            },
            OnMidnightSettlementComplete = HandleMidnightSettlementComplete,
            OnMidnightSettlementFailed = (msg) => OnMidnightSettlementFailed?.Invoke(msg),
            OnWorldPreparationProgress = HandleWorldPreparationProgress,
        };
    }

    void Start()
    {
        // 初始化场景 Anchor + 位置数据库
        SceneAnchorRegistry.Rebuild();
        LocationDatabase.Load();
        _stateStore.MarkGameplayNotReady();
        // 在场景对象就绪后连接纯状态仓库与 NPC 日程存档托管器。
        var spawner = FindObjectOfType<NpcSpawner>();
        if (spawner != null)
        {
            _stateStore.SetDailySchedulePersistence(
                spawner.WriteDailySchedulesToSave,
                spawner.RestoreDailySchedulesFromSave);
        }

        if (_autoStartGameOnConnect)
            StartCoroutine(AutoStartWhenConnected());
    }

    void HandleGameReady(GameReadyMsg msg)
    {
        _stateStore.ApplyGameReady(msg);
        var memoryStatus = msg.fresh_start ? "<color=red>全新开始(记忆已清空)</color>" : "<color=green>续玩(记忆保留)</color>";
        Debug.Log($"[GM] Game Ready: Day {CurrentTime.day} {CurrentTime.hour:D2}:{CurrentTime.minute:D2}, {NPCs.Count} NPCs — {memoryStatus}");
        foreach (var n in NPCs)
            Debug.Log($"  {n.npc_id}: {n.emotion} e={n.energy:F0} @ {n.current_location}");
        OnGameReady?.Invoke(msg);
        WorldPreparationSnapshot.is_active = false;
        WorldPreparationSnapshot.phase = "complete";
        WorldPreparationSnapshot.progress_floor = 1f;
        SystemMessageController.Instance?.CompleteLoading("世界准备完成，正在进入街区…");
    }

    void HandleLoadComplete(LoadCompleteMsg msg)
    {
        _stateStore.ApplyLoadComplete(msg);
        Debug.Log($"[GM] Load Complete: Day {CurrentTime.day} {CurrentTime.hour:D2}:{CurrentTime.minute:D2}");
        OnLoadComplete?.Invoke(msg);

        if (!string.IsNullOrEmpty(_pendingLoadSlot))
        {
            _pendingLoadSlot = null;
            SendGameStart("CONTINUE");
        }
    }

    /// <summary>
    /// 转发 Unity 权威分钟事件，不依赖后端低频时间消息。
    /// </summary>
    private void HandleAuthoritativeGameTimeChanged(GameTime gameTime)
    {
        OnAuthoritativeGameTimeChanged?.Invoke(gameTime);
    }

    /// <summary>
    /// 将后端世界准备阶段转发给唯一的加载遮罩拥有者。
    /// </summary>
    void HandleWorldPreparationProgress(WorldPreparationProgressMsg msg)
    {
        _stateStore.MarkGameplayNotReady();
        WorldPreparationSnapshot = new WorldPreparationDiagnosticSnapshot
        {
            operation_id = msg.operation_id ?? string.Empty,
            flow = msg.flow ?? string.Empty,
            phase = msg.phase ?? string.Empty,
            is_active = true,
            progress_floor = msg.progress_floor,
            failure_reason = string.Empty,
            target_game_day = msg.target_game_day,
        };
        SystemMessageController.Instance?.SetLoadingProgress(msg.message, msg.progress_floor);
        OnWorldPreparationProgress?.Invoke(msg);
    }

    /// <summary>
    /// 午夜世界准备成功后恢复主循环交互，再通知睡眠流程推进醒来和自动存档。
    /// </summary>
    void HandleMidnightSettlementComplete(MidnightSettlementCompleteMsg msg)
    {
        _stateStore.MarkGameplayReady();
        OnMidnightSettlementComplete?.Invoke(msg);
    }

    // ── 测试快捷键 ──

    void Update()
    {
        if (!WS.IsConnected) return;

        // F8 = 快进到午夜, R = 重置记忆
        // F8 后端快进已停用，午夜调试由 aisc_control 修改 Unity 权威时间。
        if (Input.GetKeyDown(KeyCode.R))
            SendGameStart("NEW_GAME");
    }

    // ── 对外 API ──

    public void SendGameStart(string mode = "NEW_GAME")
    {
        _stateStore.MarkGameplayNotReady();
        SystemMessageController.Instance?.SetLoadingProgress("正在整理初始记忆…", 0.03f);
        _commandSender.SendGameStart(mode, CurrentTime, WorldRevision);
    }

    /// <summary>
    /// 开始新游戏流程，由开始界面或其他前端入口显式触发。
    /// </summary>
    public void StartNewGameFlow()
    {
        needFlesh = true;
        SendGameStart("NEW_GAME");
        needFlesh = false;
    }

    /// <summary>
    /// 继续当前数据库中的世界状态。
    /// </summary>
    public void StartContinueFlow()
    {
        SendGameStart("CONTINUE");
    }

    /// <summary>
    /// 加载指定存档；加载完成后自动进入 CONTINUE 游戏流。
    /// </summary>
    public void StartLoadFlow(string slot)
    {
        if (string.IsNullOrWhiteSpace(slot)) slot = "1";
        _stateStore.MarkGameplayNotReady();
        _pendingLoadSlot = slot;
        SendLoad(slot);
    }

    /// <summary>
    /// 开始玩家与 NPC 的正式对话，并可附带玩家刚看到的前端表现快照。
    /// </summary>
    public void StartDialogue(string npcId, string location, NpcVisualContext visualContext = null)
    {
        if (IsDialogueActive)
        {
            Debug.LogWarning($"[对话] 已有进行中的对话，忽略新的开始请求: {CurrentDialogueNpcId}");
            return;
        }

        _stateStore.BeginDialogue(npcId);

        if (_dialogueUI != null)
        {
            var npc = _stateStore.FindNpc(npcId);
            string emotion = npc?.emotion ?? "平静";
            _dialogueUI.Open(npcId, location, emotion);
        }

        OnDialogueStarted?.Invoke(npcId);
        _pendingDialogueRequestId = $"dialogue_{Guid.NewGuid():N}";
        _pendingDialogueLocation = location;
        _pendingDialogueVisualContext = visualContext;
        SendDialogueStart(_pendingDialogueRequestId, npcId, location, visualContext);
    }

    /// <summary>
    /// 本地主动结束对话：先关闭前端 UI 并恢复交互，再通知后端收尾。
    /// </summary>
    public void EndDialogue(string reason = "player_left")
    {
        if (!IsDialogueActive) return;

        string npcId = _stateStore.CurrentDialogueNpcId;
        CloseDialogueLocal(npcId);

        if (!string.IsNullOrEmpty(npcId))
            SendDialogueEnd(npcId, reason);
    }

    /// <summary>
    /// 向后端发送玩家开始对话命令。
    /// </summary>
    public void SendDialogueStart(string requestId, string npcId, string location, NpcVisualContext visualContext = null)
    {
        _commandSender.SendDialogueStart(requestId, npcId, location, CurrentTime, WorldRevision, visualContext);
    }

    /// <summary>
    /// 在 Unity 内部应用 NPC 任务终态；正式网络同步统一使用 NPC_RUNTIME_EVENT。
    /// </summary>
    public void SendNpcActionResult(
        string requestId,
        string npcId,
        string actionId,
        string status,
        string targetLocationId,
        string actualLocationId,
        string reason)
    {
        _stateStore.ApplyNpcActionResult(npcId, status, actualLocationId);
        if (status == "succeeded")
            _gameTimeController?.SyncNow("npc_task_complete");
    }

    /// <summary>
    /// 同步 Unity 已发生的任务终态，后端仅更新推理缓存或重要记忆。
    /// </summary>
    public void SendNpcRuntimeEvent(
        string eventId,
        string requestId,
        string npcId,
        string actionId,
        string status,
        string actualLocationId,
        string reason)
    {
        _stateStore.ApplyNpcActionResult(npcId, status, actualLocationId);
        _commandSender.SendNpcRuntimeEvent(
            eventId,
            requestId,
            npcId,
            actionId,
            status,
            actualLocationId,
            reason);
    }

    /// <summary>
    /// 为 Unity 已完成会合的社交 session 请求纯语义内容。
    /// </summary>
    public void SendNpcSocialContentRequest(string requestId, string candidateId, string npcId, string targetNpcId, string actualLocationId, GameTime gameTime, long worldRevision)
    {
        _commandSender.SendNpcSocialContentRequest(requestId, candidateId, npcId, targetNpcId, actualLocationId, gameTime, worldRevision);
    }

    /// <summary>
    /// 回报 NPC-NPC 会合或播放失败。
    /// </summary>
    public void SendNpcSocialFailed(string requestId, string npcId, string targetNpcId, string actualLocationId, string reason)
    {
        _commandSender.SendNpcSocialFailed(requestId, npcId, targetNpcId, actualLocationId, reason);
    }

    /// <summary>
    /// 回报 NPC-NPC 气泡已完整播放。
    /// </summary>
    public void SendNpcSocialComplete(string requestId, string npcId, string targetNpcId, string actualLocationId)
    {
        _commandSender.SendNpcSocialComplete(requestId, npcId, targetNpcId, actualLocationId, CurrentTime, WorldRevision);
    }

    /// <summary>
    /// 将 Unity 物理社交候选交给 Python 作一次语义意愿判断。
    /// </summary>
    public void SendNpcSocialDecisionRequest(string requestId, string candidateId, string npcId, string targetNpcId, string locationId)
    {
        _commandSender.SendNpcSocialDecisionRequest(
            requestId,
            candidateId,
            npcId,
            targetNpcId,
            locationId,
            CurrentTime,
            WorldRevision);
    }

    /// <summary>
    /// 对外暴露单 NPC 日程重规划请求入口，调用方必须提供 Unity 权威剩余日程。
    /// </summary>
    public void SendNpcScheduleReplanRequest(
        string operationId,
        string npcId,
        string interactionType,
        string endReason,
        string interactionSummary,
        string[] participantIds,
        long baseScheduleRevision,
        List<NpcDailyScheduleItem> remainingSchedule,
        NpcState physicalState)
    {
        _commandSender.SendNpcScheduleReplanRequest(
            operationId,
            npcId,
            interactionType,
            endReason,
            interactionSummary,
            participantIds,
            CurrentTime,
            WorldRevision,
            baseScheduleRevision,
            remainingSchedule,
            physicalState);
    }

    public void SendDialogueEnd(string npcId, string reason = "player_left")
    {
        _commandSender.SendDialogueEnd(npcId, reason, CurrentTime, WorldRevision);
    }

    public void SendPlayerChoice(string npcId, string choiceText)
    {
        _commandSender.SendPlayerChoice(npcId, choiceText);
    }

    public void SendPlayerMove(string locationId)
    {
        _stateStore.SetPlayerLocation(locationId);
        OnPlayerLocationChanged?.Invoke(locationId);
        _commandSender.SendPlayerMove(locationId);
    }

    /// <summary>
    /// 按后端互动摘要为受影响 NPC 发起基于 Unity 权威剩余日程的重规划请求。
    /// </summary>
    private void HandleNpcScheduleReplanContext(NpcScheduleReplanContextMsg msg)
    {
        if (msg == null || msg.npc_ids == null)
            return;
        foreach (string npcId in msg.npc_ids)
        {
            if (string.IsNullOrWhiteSpace(npcId))
                continue;
            var scheduleProvider = FindObjectOfType<NpcSpawner>();
            var state = _stateStore.FindNpc(npcId);
            if (scheduleProvider == null || state == null)
                continue;
            if (!scheduleProvider.TryGetDailySchedule(npcId, out var schedule))
                continue;
            SendNpcScheduleReplanRequest(
                $"{msg.operation_id}:replan:{npcId}",
                npcId,
                msg.interaction_type,
                msg.end_reason,
                msg.interaction_summary,
                (msg.participant_ids ?? new List<string>()).ToArray(),
                schedule.ScheduleRevision,
                schedule.ExportRemaining(),
                state);
        }
    }

    public void SendSave(string slot = "1")
    {
        _saveService.Save(slot);
    }

    public void SendLoad(string slot = "1")
    {
        _saveService.Load(slot);
    }

    /// <summary>
    /// 将新存档服务结果桥接到现有开始界面事件。
    /// </summary>
    private void HandleUnitySaveFinished(string slot, bool success, string detail)
    {
        Debug.Log($"[UnitySave] slot={slot} success={success} detail={detail}");
        OnSaveComplete?.Invoke(new SaveCompleteMsg
        {
            type = "SAVE_COMPLETE",
            success = success,
            slot = slot,
        });
    }

    /// <summary>
    /// 在 Unity 主存档应用完成后桥接旧 LOAD_COMPLETE 事件。
    /// </summary>
    private void HandleUnityLoadFinished(GameSaveData data, string checkpointId)
    {
        Debug.Log($"[UnitySave] 已加载 checkpoint={checkpointId}");
        var message = new LoadCompleteMsg { type = "LOAD_COMPLETE", game_time = data.game_time };
        OnLoadComplete?.Invoke(message);
        _pendingLoadSlot = null;
        var ready = new GameReadyMsg
        {
            type = "GAME_READY",
            mode = "LOAD_GAME",
            fresh_start = false,
            game_time = data.game_time,
            weather = data.weather,
            player_location = data.player?.location_id,
            npcs = _stateStore.NPCs,
        };
        OnGameReady?.Invoke(ready);
    }

    /// <summary>
    /// 释放纯代码服务订阅，避免对象销毁后继续接收 envelope。
    /// </summary>
    void OnDestroy()
    {
        if (Instance == this) Instance = null;
        if (_saveService != null)
        {
            _saveService.SaveFinished -= HandleUnitySaveFinished;
            _saveService.LoadFinished -= HandleUnityLoadFinished;
            _saveService.Dispose();
        }
        if (_gameTimeController != null)
            _gameTimeController.TimeChanged -= HandleAuthoritativeGameTimeChanged;
    }

    /// <summary>
    /// 请求后端返回当前存档列表。
    /// </summary>
    public void RequestSavesList()
    {
        OnSavesList?.Invoke(new SavesListMsg
        {
            type = "SAVES_LIST",
            saves = _saveService.ListSaves(),
        });
    }

    /// <summary>
    /// 停止当前可交互世界并重新显示现有开始菜单。
    /// </summary>
    public void ReturnToStartMenu()
    {
        if (IsDialogueActive)
            EndDialogue("return_to_menu");
        _stateStore.MarkGameplayNotReady();
        var startMenu = FindObjectOfType<StartMenuView>(true);
        startMenu?.SetVisible(true);
        RequestSavesList();
    }

    /// <summary>
    /// 统一收口本地对话状态，供前端主动结束和后端回包结束共用。
    /// </summary>
    private void CloseDialogueLocal(string npcId)
    {
        if (!_stateStore.CanCloseDialogue(npcId))
            return;

        _stateStore.CloseDialogue();
        _pendingDialogueRequestId = null;
        _pendingDialogueLocation = null;
        _pendingDialogueVisualContext = null;

        if (_dialogueUI != null)
            _dialogueUI.Close();

        OnDialogueEnded?.Invoke(npcId);
    }

    /// <summary>
    /// 后端准备完成后确认本地会话仍有效，再发送最新现场就绪消息。
    /// </summary>
    private void HandleDialoguePrepared(DialoguePreparedMsg msg)
    {
        if (msg == null
            || msg.request_id != _pendingDialogueRequestId
            || !IsDialogueActive
            || msg.npc_id != CurrentDialogueNpcId)
        {
            Debug.LogWarning($"[对话] 忽略过期准备回包: {msg?.request_id}");
            return;
        }

        _commandSender.SendDialogueReady(
            msg.request_id,
            msg.npc_id,
            _pendingDialogueLocation,
            _pendingDialogueVisualContext);
    }

    /// <summary>
    /// 兼容旧直连链路：启用时等待 WS 接通后自动开局。
    /// </summary>
    private IEnumerator AutoStartWhenConnected()
    {
        yield return new WaitUntil(() => WS.IsConnected || WS.HasConnectAttemptFinished);
        if (!WS.IsConnected)
        {
            Debug.LogError($"[GM] WebSocket 未建立，自动启动中止: {WS.LastConnectionError}");
            yield break;
        }

        yield return new WaitForSeconds(0.3f);
        var mode = needFlesh ? "NEW_GAME" : _autoStartMode;
        needFlesh = false;
        Debug.Log($"[GM] 自动发送 GAME_START ({mode})...");
        SendGameStart(mode);
    }
}
