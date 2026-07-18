using UnityEngine;

/// <summary>
/// 在 24 个整点颜色节点之间平滑插值并驱动现有光照遮罩。
/// </summary>
public sealed class DayNightView : MonoBehaviour
{
    [SerializeField] private GameTimeController _controller;
    [SerializeField] private SpriteRenderer _targetRenderer;
    [SerializeField] private Color[] _hourlyColors = new Color[24];

    /// <summary>
    /// 订阅时间事件并检查 24 小时调色板配置。
    /// </summary>
    private void Start()
    {
        if (_controller == null)
            _controller = FindObjectOfType<GameTimeController>();
        if (_targetRenderer == null)
            _targetRenderer = GetComponent<SpriteRenderer>();
        if (_controller == null || _targetRenderer == null)
            return;

        _controller.TimeChanged += Render;
        Render(_controller.CurrentTime);
    }

    /// <summary>
    /// 使用分钟比例在当前整点与下一整点颜色间插值。
    /// </summary>
    private void Render(GameTime value)
    {
        if (value == null || _targetRenderer == null || _hourlyColors == null || _hourlyColors.Length != 24)
            return;

        int hour = Mathf.Clamp(value.hour, 0, 23);
        int nextHour = (hour + 1) % 24;
        _targetRenderer.color = Color.Lerp(_hourlyColors[hour], _hourlyColors[nextHour], value.minute / 60f);
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
