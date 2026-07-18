using System;
using UnityEngine;

/// <summary>
/// 推进 Unity 权威时间，并在关键节点覆盖 Python 镜像时钟。
/// 当前 Python 镜像协议已停用，时间只随具体 brain request 发送。
/// </summary>
public sealed class GameTimeController : MonoBehaviour
{
    private enum FlowProfile
    {
        Test,
        Production,
    }

    [SerializeField] private FlowProfile _flowProfile = FlowProfile.Test;
    [SerializeField] private float _testDayRealSeconds = 300f;
    [SerializeField] private float _productionDayRealSeconds = 1800f;

    public GameTime CurrentTime => _model.CreateSnapshot();
    public float SecondsPerGameMinute => ActiveDayRealSeconds / 1440f;
    public bool IsRunning { get; private set; }

    public event Action<GameTime> TimeChanged;
    public event Action<GameTime> DayChanged;

    private readonly GameTimeModel _model = new GameTimeModel();
    private GameCommandSender _commandSender;
    private GameManager _gameManager;
    private PauseController _pauseController;

    private float ActiveDayRealSeconds => _flowProfile == FlowProfile.Test
        ? Mathf.Max(1f, _testDayRealSeconds)
        : Mathf.Max(1f, _productionDayRealSeconds);

    /// <summary>
    /// 绑定同一生命周期对象上的协议和暂停组件。
    /// </summary>
    private void Awake()
    {
        var webSocketClient = GetComponent<WebSocketClient>();
        if (webSocketClient != null)
            _commandSender = new GameCommandSender(webSocketClient);
        _pauseController = GetComponent<PauseController>();
    }

    /// <summary>
    /// 在 GameManager 完成 Awake 后订阅游戏生命周期。
    /// </summary>
    private void Start()
    {
        _gameManager = GameManager.Instance;
        if (_gameManager == null)
            return;

        _gameManager.OnGameReady += HandleGameReady;
        _gameManager.OnLoadComplete += HandleLoadComplete;
    }

    /// <summary>
    /// 每帧仅由 Unity 推进时间；暂停时不累计经过时间。
    /// </summary>
    private void Update()
    {
        if (!IsRunning || (_pauseController != null && _pauseController.IsDomainPaused(PauseTimeDomain.Gameplay)))
            return;

        int previousDay = _model.Day;
        int previousHour = _model.Hour;
        int advancedMinutes = _model.Advance(Time.deltaTime, SecondsPerGameMinute);
        if (advancedMinutes <= 0)
            return;

        GameTime snapshot = _model.CreateSnapshot();
        TimeChanged?.Invoke(snapshot);

        if (snapshot.day != previousDay)
        {
            DayChanged?.Invoke(snapshot);
        }
    }

    /// <summary>
    /// 新游戏固定从第 1 天 08:00 开始，续玩兼容接收现有世界快照后立即回写权威值。
    /// </summary>
    private void HandleGameReady(GameReadyMsg message)
    {
        if (message != null && message.fresh_start)
            _model.Set(1, 8, 0, message.weather);
        else
            _model.Set(message?.game_time);

        IsRunning = true;
        PublishAndSync("game_ready");
    }

    /// <summary>
    /// 读档后应用 Unity 主存档中的时间并覆盖 Python 镜像。
    /// </summary>
    private void HandleLoadComplete(LoadCompleteMsg message)
    {
        _model.Set(message?.game_time);
        IsRunning = true;
        PublishAndSync("load_complete");
    }

    /// <summary>
    /// 为睡眠和诊断流程提供受控的权威时间写入口。
    /// </summary>
    public void SetTime(int day, int hour, int minute, string weather, string reason)
    {
        int previousDay = _model.Day;
        _model.Set(day, hour, minute, weather);
        GameTime snapshot = _model.CreateSnapshot();
        TimeChanged?.Invoke(snapshot);
        if (snapshot.day != previousDay)
            DayChanged?.Invoke(snapshot);
        SyncNow(reason);
    }

    /// <summary>
    /// 在任务完成、保存等关键节点主动覆盖 Python 镜像时钟。
    /// 当前实现保留调用兼容，但不再发送独立同步协议。
    /// </summary>
    public void SyncNow(string reason)
    {
        // 时间只随具体 brain request 发送，不维护 Python 全局镜像。
    }

    /// <summary>
    /// 发布当前状态并立即同步，供生命周期入口复用。
    /// </summary>
    private void PublishAndSync(string reason)
    {
        TimeChanged?.Invoke(CurrentTime);
    }

    /// <summary>
    /// 释放 GameManager 事件订阅。
    /// </summary>
    private void OnDestroy()
    {
        if (_gameManager == null)
            return;

        _gameManager.OnGameReady -= HandleGameReady;
        _gameManager.OnLoadComplete -= HandleLoadComplete;
    }
}
