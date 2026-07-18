using System.Collections.Generic;

/// <summary>
/// 集中维护稳定暂停来源会影响的时间域，避免消费者散落来源判断。
/// </summary>
public static class PauseSourcePolicy
{
    private const PauseTimeDomain WorldPause = PauseTimeDomain.Gameplay | PauseTimeDomain.FX;

    private static readonly IReadOnlyDictionary<string, PauseTimeDomain> DomainsBySource =
        new Dictionary<string, PauseTimeDomain>(System.StringComparer.Ordinal)
        {
            [PauseSources.Dialogue] = WorldPause,
            [PauseSources.Inventory] = WorldPause,
            [PauseSources.PauseMenu] = WorldPause,
            [PauseSources.BlockingMessage] = WorldPause,
            [PauseSources.LoadingOverlay] = WorldPause,
            [PauseSources.SleepFlow] = WorldPause,
            [PauseSources.SaveManagement] = WorldPause,
            [PauseSources.DiagnosticsTest] = WorldPause,
        };

    /// <summary>
    /// 返回暂停来源影响的域；未知旧来源按世界暂停处理以保持兼容。
    /// </summary>
    public static PauseTimeDomain GetDomains(string source)
    {
        string normalized = PauseModel.NormalizeSource(source);
        return DomainsBySource.TryGetValue(normalized, out PauseTimeDomain domains)
            ? domains
            : WorldPause;
    }
}
