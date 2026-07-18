using System;

/// <summary>
/// 标识可由暂停来源独立控制的运行时间域。
/// </summary>
[Flags]
public enum PauseTimeDomain
{
    None = 0,
    Gameplay = 1 << 0,
    UI = 1 << 1,
    FX = 1 << 2,
    All = Gameplay | UI | FX,
}
