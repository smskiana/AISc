using System;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// 管理系统消息 Canvas 的静态控件和显示状态。
/// </summary>
public sealed class SystemMessageView : MonoBehaviour
{
    [Header("普通提醒")]
    [SerializeField] private GameObject _noticePanel;
    [SerializeField] private TMP_Text _noticeText;

    [Header("阻塞弹窗")]
    [SerializeField] private GameObject _blockingPanel;
    [SerializeField] private TMP_Text _blockingText;
    [SerializeField] private Button _primaryButton;
    [SerializeField] private TMP_Text _primaryButtonText;
    [SerializeField] private Button _secondaryButton;
    [SerializeField] private TMP_Text _secondaryButtonText;

    [Header("加载遮罩")]
    [SerializeField] private GameObject _loadingOverlay;
    [SerializeField] private TMP_Text _loadingTitleText;
    [SerializeField] private TMP_Text _loadingText;
    [SerializeField] private Slider _loadingProgressBar;

    private float _visualProgress;
    private float _targetProgress;
    private bool _loadingCompletionRequested;

    public bool IsLoadingProgressComplete => _loadingCompletionRequested
        && _visualProgress >= 0.999f;

    /// <summary>
    /// 初始化所有动态面板为隐藏状态。
    /// </summary>
    private void Awake()
    {
        HideNotice();
        HideBlocking();
        SetLoading(false, string.Empty);
    }

    /// <summary>
    /// 显示一条不阻塞游戏的普通提醒。
    /// </summary>
    public void ShowNotice(string message)
    {
        if (_noticeText != null)
            _noticeText.text = message ?? string.Empty;
        if (_noticePanel != null)
            _noticePanel.SetActive(true);
    }

    /// <summary>
    /// 隐藏当前普通提醒。
    /// </summary>
    public void HideNotice()
    {
        if (_noticePanel != null)
            _noticePanel.SetActive(false);
    }

    /// <summary>
    /// 显示单按钮或双按钮阻塞弹窗，并绑定本次业务动作。
    /// </summary>
    public void ShowBlocking(
        string message,
        string primaryLabel,
        Action primaryAction,
        string secondaryLabel,
        Action secondaryAction)
    {
        if (_blockingText != null)
            _blockingText.text = message ?? string.Empty;

        BindButton(_primaryButton, _primaryButtonText, primaryLabel, primaryAction, true);
        BindButton(
            _secondaryButton,
            _secondaryButtonText,
            secondaryLabel,
            secondaryAction,
            !string.IsNullOrWhiteSpace(secondaryLabel));

        if (_blockingPanel != null)
            _blockingPanel.SetActive(true);
    }

    /// <summary>
    /// 隐藏阻塞弹窗并清理旧按钮监听。
    /// </summary>
    public void HideBlocking()
    {
        if (_primaryButton != null)
            _primaryButton.onClick.RemoveAllListeners();
        if (_secondaryButton != null)
            _secondaryButton.onClick.RemoveAllListeners();
        if (_blockingPanel != null)
            _blockingPanel.SetActive(false);
    }

    /// <summary>
    /// 切换覆盖全屏的加载遮罩和提示文字。
    /// </summary>
    public void SetLoading(bool visible, string message)
    {
        if (_loadingText != null)
            _loadingText.text = message ?? string.Empty;
        if (visible)
        {
            _visualProgress = 0.03f;
            _targetProgress = 0.03f;
            _loadingCompletionRequested = false;
            ApplyLoadingProgress();
        }
        if (_loadingOverlay != null)
            _loadingOverlay.SetActive(visible);
    }

    /// <summary>
    /// 接收阶段文案和后端完成下限，只将其作为视觉进度的缓动目标。
    /// </summary>
    public void SetLoadingProgress(string message, float progressFloor, bool completed)
    {
        if (_loadingTitleText != null)
            _loadingTitleText.text = completed ? "世界已准备完成" : "正在准备世界";
        if (_loadingText != null)
            _loadingText.text = message ?? string.Empty;
        _loadingCompletionRequested = completed;
        _targetProgress = completed
            ? 1f
            : Mathf.Max(_targetProgress, Mathf.Clamp(progressFloor, 0.03f, 0.95f));
    }

    /// <summary>
    /// 使用 UI 时间域平滑加载条，避免 Gameplay 暂停时动画冻结。
    /// </summary>
    public void TickLoading()
    {
        _visualProgress = Mathf.MoveTowards(
            _visualProgress,
            _targetProgress,
            PauseClock.GetDeltaTime(PauseTimeDomain.UI) * (_loadingCompletionRequested ? 2.5f : 0.12f));
        ApplyLoadingProgress();
    }

    /// <summary>
    /// 将当前视觉进度写入已资产化的 Slider。
    /// </summary>
    private void ApplyLoadingProgress()
    {
        if (_loadingProgressBar != null)
            _loadingProgressBar.value = _visualProgress;
    }

    /// <summary>
    /// 为资产化按钮设置本次显示所需的文字、显隐和回调。
    /// </summary>
    private static void BindButton(Button button, TMP_Text label, string text, Action action, bool visible)
    {
        if (button == null)
            return;

        button.onClick.RemoveAllListeners();
        button.gameObject.SetActive(visible);
        if (!visible)
            return;

        if (label != null)
            label.text = text ?? string.Empty;
        if (action != null)
            button.onClick.AddListener(() => action());
    }
}
