using System;
using UnityEngine;

/// <summary>
/// 统一处理多来源暂停、Unity 时间缩放和 Python 镜像时钟同步。
/// 当前 Python 镜像同步已停用，暂停状态只由 Unity 本地持有。
/// </summary>
public sealed class PauseController : MonoBehaviour
{
    public static PauseController Instance { get; private set; }

    [SerializeField] private bool _controlUnityTimeScale = true;

    public bool IsPaused => _model.IsPaused;
    public string[] ActiveSources => _model.CreateSnapshot();

    public event Action<bool, string[]> PauseChanged;
    public event Action<PauseTimeDomain> DomainPauseChanged;

    private readonly PauseModel _model = new PauseModel();
    private GameCommandSender _commandSender;
    private GameManager _gameManager;
    private float _resumeTimeScale = 1f;

    /// <summary>
    /// 绑定同一生命周期对象上的网络客户端，但不要求 GameManager 持有暂停状态。
    /// </summary>
    private void Awake()
    {
        Instance = this;
        var webSocketClient = GetComponent<WebSocketClient>();
        if (webSocketClient != null)
            _commandSender = new GameCommandSender(webSocketClient);
    }

    /// <summary>
    /// 在所有 Awake 完成后绑定对话事件，避免依赖组件初始化顺序。
    /// </summary>
    private void Start()
    {
        BindGameManager();
    }

    /// <summary>
    /// 申请一个暂停来源；重复申请同一来源不会重复改变全局状态。
    /// </summary>
    public void RequestPause(string source)
    {
        PauseTimeDomain before = CreatePausedDomains();
        if (!_model.Add(source, PauseSourcePolicy.GetDomains(source)))
            return;

        ApplyState(before);
    }

    /// <summary>
    /// 释放一个暂停来源；其他来源仍存在时保持暂停。
    /// </summary>
    public void ReleasePause(string source)
    {
        PauseTimeDomain before = CreatePausedDomains();
        if (!_model.Remove(source))
            return;

        ApplyState(before);
    }

    /// <summary>
    /// 判断指定时间域是否被任意活动来源暂停。
    /// </summary>
    public bool IsDomainPaused(PauseTimeDomain domain)
    {
        return _model.IsDomainPaused(domain);
    }

    /// <summary>
    /// 应用集合变化，并仅在最终暂停状态切换时同步全局时钟。
    /// </summary>
    private void ApplyState(PauseTimeDomain before)
    {
        bool isPaused = _model.IsPaused;
        string[] sources = _model.CreateSnapshot();
        PauseTimeDomain after = CreatePausedDomains();
        PauseTimeDomain changedDomains = before ^ after;

        if ((changedDomains & PauseTimeDomain.Gameplay) != 0)
        {
            if (_controlUnityTimeScale)
            {
                if ((after & PauseTimeDomain.Gameplay) != 0)
                {
                    if (Time.timeScale > 0f)
                        _resumeTimeScale = Time.timeScale;
                    Time.timeScale = 0f;
                }
                else
                {
                    Time.timeScale = _resumeTimeScale > 0f ? _resumeTimeScale : 1f;
                }
            }

        }

        if (changedDomains != PauseTimeDomain.None)
            DomainPauseChanged?.Invoke(changedDomains);
        PauseChanged?.Invoke(isPaused, sources);
    }

    /// <summary>
    /// 构造当前三个时间域的位掩码快照。
    /// </summary>
    private PauseTimeDomain CreatePausedDomains()
    {
        PauseTimeDomain domains = PauseTimeDomain.None;
        if (_model.IsDomainPaused(PauseTimeDomain.Gameplay)) domains |= PauseTimeDomain.Gameplay;
        if (_model.IsDomainPaused(PauseTimeDomain.UI)) domains |= PauseTimeDomain.UI;
        if (_model.IsDomainPaused(PauseTimeDomain.FX)) domains |= PauseTimeDomain.FX;
        return domains;
    }

    /// <summary>
    /// 返回实际影响指定域的稳定来源列表。
    /// </summary>
    public string[] CreateDomainSources(PauseTimeDomain domain)
    {
        string[] sources = _model.CreateSnapshot();
        return Array.FindAll(sources, source => (PauseSourcePolicy.GetDomains(source) & domain) != 0);
    }

    /// <summary>
    /// 订阅现有玩家对话生命周期，使对话成为普通暂停来源之一。
    /// </summary>
    private void BindGameManager()
    {
        _gameManager = GameManager.Instance;
        if (_gameManager == null)
            return;

        _gameManager.OnDialogueStarted += HandleDialogueStarted;
        _gameManager.OnDialogueEnded += HandleDialogueEnded;
        if (_gameManager.IsDialogueActive)
            RequestPause(PauseSources.Dialogue);
    }

    /// <summary>
    /// 玩家对话开始时申请对话暂停来源。
    /// </summary>
    private void HandleDialogueStarted(string npcId)
    {
        RequestPause(PauseSources.Dialogue);
    }

    /// <summary>
    /// 玩家对话结束时只释放对话自己的暂停来源。
    /// </summary>
    private void HandleDialogueEnded(string npcId)
    {
        ReleasePause(PauseSources.Dialogue);
    }

    /// <summary>
    /// 释放事件订阅，避免持久对象销毁后残留回调。
    /// </summary>
    private void OnDestroy()
    {
        if (Instance == this)
            Instance = null;
        if (_gameManager != null)
        {
            _gameManager.OnDialogueStarted -= HandleDialogueStarted;
            _gameManager.OnDialogueEnded -= HandleDialogueEnded;
        }

        if (_controlUnityTimeScale && _model.IsDomainPaused(PauseTimeDomain.Gameplay))
            Time.timeScale = _resumeTimeScale > 0f ? _resumeTimeScale : 1f;
    }
}
