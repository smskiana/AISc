using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 顺序调度普通提醒和阻塞弹窗，并统一管理加载遮罩暂停来源。
/// </summary>
public sealed class SystemMessageController : MonoBehaviour
{
    private sealed class BlockingRequest
    {
        public string Message;
        public string PrimaryLabel;
        public Action PrimaryAction;
        public string SecondaryLabel;
        public Action SecondaryAction;
    }

    public static SystemMessageController Instance { get; private set; }
    public bool IsBlocking => _activeBlocking != null;
    public bool IsLoading => _loading;

    [SerializeField] private SystemMessageView _view;
    [SerializeField] private float _noticeDurationSeconds = 3f;

    private readonly Queue<string> _noticeQueue = new Queue<string>();
    private readonly Queue<BlockingRequest> _blockingQueue = new Queue<BlockingRequest>();
    private PauseController _pauseController;
    private BlockingRequest _activeBlocking;
    private float _noticeRemaining;
    private bool _noticeVisible;
    private bool _loading;
    private bool _loadingCompletionRequested;

    /// <summary>
    /// 建立全局消息入口并绑定独立暂停模块。
    /// </summary>
    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }

        Instance = this;
        _pauseController = FindObjectOfType<PauseController>();
    }

    /// <summary>
    /// 使用未缩放时间推进普通提醒，阻塞弹窗存在时保持等待。
    /// </summary>
    private void Update()
    {
        if (_loading)
            _view?.TickLoading();
        if (_activeBlocking != null || _loading)
            return;

        if (_noticeVisible)
        {
            _noticeRemaining -= PauseClock.GetDeltaTime(PauseTimeDomain.UI);
            if (_noticeRemaining <= 0f)
            {
                _view?.HideNotice();
                _noticeVisible = false;
            }
        }

        if (!_noticeVisible && _noticeQueue.Count > 0)
            ShowNextNotice();
    }

    /// <summary>
    /// 将普通提醒加入先进先出队列。
    /// </summary>
    public void ShowNotice(string message)
    {
        _noticeQueue.Enqueue(message ?? string.Empty);
        if (!_noticeVisible && _activeBlocking == null && !_loading)
            ShowNextNotice();
    }

    /// <summary>
    /// 将单按钮或双按钮阻塞弹窗加入先进先出队列。
    /// </summary>
    public void ShowBlocking(
        string message,
        string primaryLabel,
        Action primaryAction,
        string secondaryLabel = null,
        Action secondaryAction = null)
    {
        _blockingQueue.Enqueue(new BlockingRequest
        {
            Message = message ?? string.Empty,
            PrimaryLabel = primaryLabel ?? "确定",
            PrimaryAction = primaryAction,
            SecondaryLabel = secondaryLabel,
            SecondaryAction = secondaryAction,
        });

        TryShowNextBlocking();
    }

    /// <summary>
    /// 显示或关闭加载遮罩，并只管理加载自己的暂停来源。
    /// </summary>
    public void SetLoading(bool visible, string message = "正在处理...")
    {
        if (_loading == visible)
        {
            if (visible)
                _view?.SetLoading(true, message);
            return;
        }

        _loading = visible;
        _loadingCompletionRequested = false;
        _view?.SetLoading(visible, message);
        if (visible)
            _pauseController?.RequestPause(PauseSources.LoadingOverlay);
        else
            _pauseController?.ReleasePause(PauseSources.LoadingOverlay);

        if (!visible)
            TryShowNextBlocking();
    }

    /// <summary>
    /// 更新世界准备阶段；进度上限由 View 保证在成功前不会达到 100%。
    /// </summary>
    public void SetLoadingProgress(string message, float progressFloor)
    {
        if (!_loading)
            SetLoading(true, message);
        _view?.SetLoadingProgress(message, progressFloor, false);
    }

    /// <summary>
    /// 播放加载完成的视觉收口，再释放 LoadingOverlay 暂停来源。
    /// </summary>
    public void CompleteLoading(string message = "正在进入街区…")
    {
        if (!_loading || _loadingCompletionRequested)
            return;
        _loadingCompletionRequested = true;
        _view?.SetLoadingProgress(message, 1f, true);
        StartCoroutine(CompleteLoadingAfterVisual());
    }

    /// <summary>
    /// 使用 UI 时间域等待进度条收口，避免暂停状态影响完成动画。
    /// </summary>
    private System.Collections.IEnumerator CompleteLoadingAfterVisual()
    {
        while (_view != null && !_view.IsLoadingProgressComplete)
            yield return null;
        SetLoading(false);
    }

    /// <summary>
    /// 显示下一条普通提醒并重置三秒计时。
    /// </summary>
    private void ShowNextNotice()
    {
        if (_noticeQueue.Count == 0)
            return;

        _noticeVisible = true;
        _noticeRemaining = Mathf.Max(0.1f, _noticeDurationSeconds);
        _view?.ShowNotice(_noticeQueue.Dequeue());
    }

    /// <summary>
    /// 在无加载遮罩和活动弹窗时显示下一条阻塞请求。
    /// </summary>
    private void TryShowNextBlocking()
    {
        if (_loading || _activeBlocking != null || _blockingQueue.Count == 0)
            return;

        _activeBlocking = _blockingQueue.Dequeue();
        if (_noticeVisible)
        {
            _view?.HideNotice();
            _noticeVisible = false;
        }

        _pauseController?.RequestPause(PauseSources.BlockingMessage);
        _view?.ShowBlocking(
            _activeBlocking.Message,
            _activeBlocking.PrimaryLabel,
            () => ResolveBlocking(true),
            _activeBlocking.SecondaryLabel,
            () => ResolveBlocking(false));
    }

    /// <summary>
    /// 执行所选业务回调、释放当前弹窗暂停来源并继续队列。
    /// </summary>
    private void ResolveBlocking(bool primary)
    {
        BlockingRequest resolved = _activeBlocking;
        if (resolved == null)
            return;

        _activeBlocking = null;
        _view?.HideBlocking();
        _pauseController?.ReleasePause(PauseSources.BlockingMessage);

        if (primary)
            resolved.PrimaryAction?.Invoke();
        else
            resolved.SecondaryAction?.Invoke();

        TryShowNextBlocking();
    }

    /// <summary>
    /// 清理全局入口和本模块仍持有的暂停来源。
    /// </summary>
    private void OnDestroy()
    {
        if (Instance == this)
            Instance = null;
        _pauseController?.ReleasePause(PauseSources.BlockingMessage);
        _pauseController?.ReleasePause(PauseSources.LoadingOverlay);
    }
}
