using UnityEngine;

/// <summary>
/// 为非游戏逻辑消费者提供按时间域裁剪后的帧时间。
/// </summary>
public static class PauseClock
{
    /// <summary>
    /// 返回指定域的非缩放帧时间；该域暂停时返回零。
    /// </summary>
    public static float GetDeltaTime(PauseTimeDomain domain)
    {
        PauseController controller = PauseController.Instance;
        return controller != null && controller.IsDomainPaused(domain)
            ? 0f
            : Time.unscaledDeltaTime;
    }
}
