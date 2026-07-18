using System;

/// <summary>
/// 保存并推进 Unity 权威游戏时间，不引用其他功能域 Model。
/// </summary>
public sealed class GameTimeModel
{
    public int Day { get; private set; } = 1;
    public int Hour { get; private set; } = 8;
    public int Minute { get; private set; }
    public string Weather { get; private set; } = "sunny";

    private double _accumulatedRealSeconds;

    /// <summary>
    /// 用经过校验的状态覆盖当前时间，并清空未完成的分钟累计。
    /// </summary>
    public void Set(int day, int hour, int minute, string weather)
    {
        Day = Math.Max(1, day);
        Hour = Math.Max(0, Math.Min(23, hour));
        Minute = Math.Max(0, Math.Min(59, minute));
        Weather = string.IsNullOrWhiteSpace(weather) ? "sunny" : weather;
        _accumulatedRealSeconds = 0d;
    }

    /// <summary>
    /// 应用协议或存档中的时间快照。
    /// </summary>
    public void Set(GameTime value)
    {
        if (value == null)
            return;

        Set(value.day, value.hour, value.minute, value.weather);
    }

    /// <summary>
    /// 根据现实经过时间推进完整游戏分钟，并返回推进的分钟数。
    /// </summary>
    public int Advance(double realDeltaSeconds, double secondsPerGameMinute)
    {
        if (realDeltaSeconds <= 0d || secondsPerGameMinute <= 0d)
            return 0;

        _accumulatedRealSeconds += realDeltaSeconds;
        int advancedMinutes = 0;
        while (_accumulatedRealSeconds >= secondsPerGameMinute)
        {
            _accumulatedRealSeconds -= secondsPerGameMinute;
            AdvanceOneMinute();
            advancedMinutes++;
        }

        return advancedMinutes;
    }

    /// <summary>
    /// 创建与协议、存档兼容的独立时间快照。
    /// </summary>
    public GameTime CreateSnapshot()
    {
        return new GameTime
        {
            day = Day,
            hour = Hour,
            minute = Minute,
            weather = Weather,
        };
    }

    /// <summary>
    /// 推进一分钟，并在 24:00 直接进入下一天 00:00。
    /// </summary>
    private void AdvanceOneMinute()
    {
        Minute++;
        if (Minute < 60)
            return;

        Minute = 0;
        Hour++;
        if (Hour < 24)
            return;

        Hour = 0;
        Day++;
    }
}
