using System.Collections;
using UnityEngine;
using TMPro;

/// <summary>
/// 世界空间对话气泡 UI — 挂在 NPC 子 Canvas 上。
/// 支持淡入/淡出动画，duration 后自动隐藏。
///
/// 预制体结构（用户搭建）:
///   BubbleCanvas (Canvas, World Space, 挂在 NPC 子物体)
///   └── BubblePanel (Image 背景)
///       └── BubbleText (TextMeshPro)
/// </summary>
public class BubbleUI : MonoBehaviour
{
    [Header("UI 引用 — 填充预制体引用")]
    [SerializeField] private GameObject _panel;
    [SerializeField] private UnityEngine.UI.Image _background;
    [SerializeField] private TMP_Text _text;

    [Header("动画参数")]
    [SerializeField] private float _fadeDuration = 0.3f;
    [SerializeField] private float _defaultDuration = 4.0f;

    [Header("样式")]
    [SerializeField] private Vector2 _offset = new Vector2(0f, 1.8f);  // 头顶偏移

    public bool IsShowing { get; private set; }

    private Coroutine _hideRoutine;
    private Coroutine _fadeRoutine;

    // ── 初始化 ──

    private void Awake()
    {
        if (_panel != null)
            _panel.gameObject.SetActive(false);
    }

    // ── 显示/隐藏 ──

    /// <summary>
    /// 显示气泡文字。如果已有气泡在显示，替换内容并重置计时。
    /// </summary>
    /// <param name="text">气泡文字</param>
    /// <param name="durationSec">显示时长（秒），0 则使用默认值</param>
    public void Show(string text, float durationSec = 0f)
    {
        if (durationSec <= 0f) durationSec = _defaultDuration;

        if (_text != null)
            _text.text = text;

        // 如果已有气泡，重置计时
        if (IsShowing && _hideRoutine != null)
        {
            StopCoroutine(_hideRoutine);
            _hideRoutine = StartCoroutine(AutoHide(durationSec));
            return;
        }

        // 显示
        IsShowing = true;
        if (_panel != null)
            _panel.gameObject.SetActive(true);

        // 淡入
        if (_fadeRoutine != null) StopCoroutine(_fadeRoutine);
        _fadeRoutine = StartCoroutine(FadeIn());

        // 自动隐藏
        _hideRoutine = StartCoroutine(AutoHide(durationSec));
    }

    /// <summary>
    /// 立即隐藏气泡。
    /// </summary>
    public void Hide()
    {
        IsShowing = false;

        if (_hideRoutine != null)
        {
            StopCoroutine(_hideRoutine);
            _hideRoutine = null;
        }
        if (_fadeRoutine != null)
        {
            StopCoroutine(_fadeRoutine);
            _fadeRoutine = null;
        }

        if (_panel != null)
            _panel.gameObject.SetActive(false);
    }

    // ── 协程 ──

    private IEnumerator FadeIn()
    {
        float elapsed = 0f;

        // 从透明开始
        if (_background != null)
        {
            var bgColor = _background.color;
            bgColor.a = 0f;
            _background.color = bgColor;
        }
        if (_text != null)
        {
            var txtColor = _text.color;
            txtColor.a = 0f;
            _text.color = txtColor;
        }

        while (elapsed < _fadeDuration)
        {
            elapsed += PauseClock.GetDeltaTime(PauseTimeDomain.UI);
            float t = Mathf.Clamp01(elapsed / _fadeDuration);

            if (_background != null)
            {
                var c = _background.color;
                c.a = Mathf.Lerp(0f, 1f, t);
                _background.color = c;
            }
            if (_text != null)
            {
                var c = _text.color;
                c.a = Mathf.Lerp(0f, 1f, t);
                _text.color = c;
            }
            yield return null;
        }
    }

    private IEnumerator AutoHide(float delay)
    {
        float remaining = delay;
        while (remaining > 0f)
        {
            remaining -= PauseClock.GetDeltaTime(PauseTimeDomain.UI);
            yield return null;
        }

        // 淡出
        float elapsed = 0f;
        while (elapsed < _fadeDuration)
        {
            elapsed += PauseClock.GetDeltaTime(PauseTimeDomain.UI);
            float t = Mathf.Clamp01(elapsed / _fadeDuration);

            if (_background != null)
            {
                var c = _background.color;
                c.a = Mathf.Lerp(1f, 0f, t);
                _background.color = c;
            }
            if (_text != null)
            {
                var c = _text.color;
                c.a = Mathf.Lerp(1f, 0f, t);
                _text.color = c;
            }
            yield return null;
        }

        Hide();
    }
}
