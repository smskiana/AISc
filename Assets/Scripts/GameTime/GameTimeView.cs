using TMPro;
using UnityEngine;

/// <summary>
/// 将权威时间格式化为玩家 HUD 文本。
/// </summary>
public sealed class GameTimeView : MonoBehaviour
{
    [SerializeField] private GameTimeController _controller;
    [SerializeField] private TMP_Text _timeText;

    /// <summary>
    /// 订阅时间变化并立即刷新当前值。
    /// </summary>
    private void Start()
    {
        if (_controller == null)
            _controller = FindObjectOfType<GameTimeController>();
        if (_controller == null)
            return;

        _controller.TimeChanged += Render;
        Render(_controller.CurrentTime);
    }

    /// <summary>
    /// 按 `[第X天]-am/pm-HH:MM` 显示 12 小时制时间。
    /// </summary>
    private void Render(GameTime value)
    {
        if (_timeText == null || value == null)
            return;

        string period = value.hour < 12 ? "am" : "pm";
        int displayHour = value.hour % 12;
        if (displayHour == 0)
            displayHour = 12;
        _timeText.text = $"[第{value.day}天]-{period}-{displayHour:00}:{value.minute:00}";
    }

    /// <summary>
    /// 释放时间事件订阅。
    /// </summary>
    private void OnDestroy()
    {
        if (_controller != null)
            _controller.TimeChanged -= Render;
    }
}
