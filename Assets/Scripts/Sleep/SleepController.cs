using System.Collections;
using UnityEngine;

/// <summary>
/// 统筹主动或强制睡眠、Python 午夜结算、次日醒来和自动存档。
/// </summary>
public sealed class SleepController : MonoBehaviour
{
    [SerializeField] private GameTimeController _gameTimeController;
    [SerializeField] private NpcSpawner _npcSpawner;
    [SerializeField] private Transform _player;
    [SerializeField] private Transform _wakeAnchor;
    [SerializeField] private float _settlementTimeoutRealSeconds = 600f;

    public bool IsSleeping { get; private set; }

    private PauseController _pauseController;
    private UnitySaveService _saveService;
    private GameCommandSender _commandSender;
    private WebSocketClient _webSocket;
    private int _forcedSleepDay = -1;
    private Coroutine _timeoutRoutine;
    private string _nextWeather = "sunny";

    /// <summary>
    /// 绑定时间、协议、暂停、存档和午夜结果事件。
    /// </summary>
    private void Start()
    {
        if (_gameTimeController == null) _gameTimeController = FindObjectOfType<GameTimeController>();
        if (_npcSpawner == null) _npcSpawner = FindObjectOfType<NpcSpawner>();
        if (_player == null)
        {
            var playerController = FindObjectOfType<PlayerController>();
            if (playerController != null) _player = playerController.transform;
        }
        _pauseController = PauseController.Instance;
        _saveService = GameManager.Instance?.SaveService;
        _webSocket = GameManager.Instance?.WS;
        if (_webSocket != null) _commandSender = new GameCommandSender(_webSocket);

        if (_gameTimeController != null)
            _gameTimeController.TimeChanged += HandleTimeChanged;
        if (GameManager.Instance != null)
        {
            GameManager.Instance.OnMidnightSettlementComplete += HandleSettlementComplete;
            GameManager.Instance.OnMidnightSettlementFailed += HandleSettlementFailed;
        }
        if (_saveService != null)
            _saveService.SaveFinished += HandleAutoSaveFinished;
    }

    /// <summary>
    /// 显示睡到明天的主动睡眠确认。
    /// </summary>
    public void RequestVoluntarySleep()
    {
        if (IsSleeping) return;
        SystemMessageController.Instance?.ShowBlocking(
            "确认睡到明天吗？",
            "睡觉",
            () => BeginSleep(false),
            "取消");
    }

#if UNITY_EDITOR
    /// <summary>
    /// 供编辑器诊断白名单直接触发正式午夜结算，不经过确认弹窗。
    /// </summary>
    public bool StartMidnightForEditorDiagnostics()
    {
        if (IsSleeping || _commandSender == null)
            return false;
        BeginSleep(false);
        return IsSleeping;
    }
#endif

    /// <summary>
    /// 在每天 23:30 首次到达时从任意地点触发强制睡眠。
    /// </summary>
    private void HandleTimeChanged(GameTime value)
    {
        if (value == null || IsSleeping || value.day == _forcedSleepDay)
            return;
        if (value.hour > 23 || (value.hour == 23 && value.minute >= 30))
        {
            _forcedSleepDay = value.day;
            BeginSleep(true);
        }
    }

    /// <summary>
    /// 申请睡眠暂停、终止 NPC 当日任务并请求 Python 完整午夜结算。
    /// </summary>
    private void BeginSleep(bool forced)
    {
        if (IsSleeping || _commandSender == null)
            return;
        IsSleeping = true;
        _pauseController?.RequestPause(PauseSources.SleepFlow);
        SystemMessageController.Instance?.SetLoading(true, forced ? "夜深了，正在返回喫茶店..." : "正在进入梦乡...");
        if (GameManager.Instance != null && GameManager.Instance.IsDialogueActive)
            GameManager.Instance.EndDialogue("sleep_started");
        _npcSpawner?.PrepareForSleep();
        _commandSender.SendMidnightSettlement(_gameTimeController?.CurrentTime);
        _timeoutRoutine = StartCoroutine(SettlementTimeout());
    }

    /// <summary>
    /// 午夜结算成功后推进次日 06:00、移动玩家并覆盖自动存档。
    /// </summary>
    private void HandleSettlementComplete(MidnightSettlementCompleteMsg message)
    {
        if (!IsSleeping) return;
        StopTimeout();
        if (string.Equals(message?.maintenance_status, "partial_failure", System.StringComparison.Ordinal))
            Debug.LogWarning($"午夜结算局部失败，已使用可用结果继续：{string.Join(",", message.failure_reasons ?? System.Array.Empty<string>())}");
        _nextWeather = string.IsNullOrWhiteSpace(message?.weather) ? "sunny" : message.weather;
        GameTime current = _gameTimeController.CurrentTime;
        _gameTimeController.SetTime(current.day + 1, 6, 0, _nextWeather, "sleep_wake");
        if (_player != null && _wakeAnchor != null)
            _player.position = _wakeAnchor.position;
        GameManager.Instance?.SendPlayerMove("player_cafe.bed");

        byte[] screenshot = FindObjectOfType<SaveScreenshotCapture>()?.CapturePng();
        _saveService.Save("auto", null, true, screenshot);
    }

    /// <summary>
    /// 午夜结算明确失败时进入致命错误流程。
    /// </summary>
    private void HandleSettlementFailed(MidnightSettlementFailedMsg message)
    {
        if (!IsSleeping) return;
        StopTimeout();
        FatalErrorController.Instance?.ShowFatal($"午夜结算失败：{message?.reason}");
    }

    /// <summary>
    /// 自动存档完成后正常醒来；失败只显示简单错误弹窗，不阻断醒来。
    /// </summary>
    private void HandleAutoSaveFinished(string slot, bool success, string detail)
    {
        if (!IsSleeping || slot != "auto")
            return;

        SystemMessageController.Instance?.SetLoading(false);
        _npcSpawner?.ResumeAfterSleep();
        _pauseController?.ReleasePause(PauseSources.SleepFlow);
        IsSleeping = false;
        if (!success)
            SystemMessageController.Instance?.ShowBlocking($"自动存档失败：{detail}", "确定", null);
    }

    /// <summary>
    /// 使用现实时间等待最多十分钟，超时进入致命错误流程。
    /// </summary>
    private IEnumerator SettlementTimeout()
    {
        yield return new WaitForSecondsRealtime(Mathf.Max(1f, _settlementTimeoutRealSeconds));
        _timeoutRoutine = null;
        if (IsSleeping)
            FatalErrorController.Instance?.ShowFatal("午夜结算等待超过 10 分钟。");
    }

    /// <summary>
    /// 停止仍在等待的午夜超时协程。
    /// </summary>
    private void StopTimeout()
    {
        if (_timeoutRoutine == null) return;
        StopCoroutine(_timeoutRoutine);
        _timeoutRoutine = null;
    }

    /// <summary>
    /// 释放事件订阅和睡眠暂停来源。
    /// </summary>
    private void OnDestroy()
    {
        StopTimeout();
        if (_gameTimeController != null)
            _gameTimeController.TimeChanged -= HandleTimeChanged;
        if (GameManager.Instance != null)
        {
            GameManager.Instance.OnMidnightSettlementComplete -= HandleSettlementComplete;
            GameManager.Instance.OnMidnightSettlementFailed -= HandleSettlementFailed;
        }
        if (_saveService != null)
            _saveService.SaveFinished -= HandleAutoSaveFinished;
        _pauseController?.ReleasePause(PauseSources.SleepFlow);
    }
}
