using System;
using System.Collections.Generic;

/// <summary>
/// 保存全局暂停来源集合，并保证同一来源的申请和释放是幂等的。
/// </summary>
public sealed class PauseModel
{
    private readonly Dictionary<string, PauseTimeDomain> _sources =
        new Dictionary<string, PauseTimeDomain>(StringComparer.Ordinal);

    public bool IsPaused => _sources.Count > 0;
    public int SourceCount => _sources.Count;
    public IReadOnlyCollection<string> Sources => _sources.Keys;

    /// <summary>
    /// 注册暂停来源；仅在集合实际变化时返回 true。
    /// </summary>
    public bool Add(string source, PauseTimeDomain domains)
    {
        string normalized = NormalizeSource(source);
        if (_sources.ContainsKey(normalized))
            return false;
        _sources.Add(normalized, domains);
        return true;
    }

    /// <summary>
    /// 释放暂停来源；仅在集合实际变化时返回 true。
    /// </summary>
    public bool Remove(string source)
    {
        return _sources.Remove(NormalizeSource(source));
    }

    /// <summary>
    /// 判断指定时间域是否被至少一个活动来源暂停。
    /// </summary>
    public bool IsDomainPaused(PauseTimeDomain domain)
    {
        foreach (PauseTimeDomain domains in _sources.Values)
        {
            if ((domains & domain) != 0)
                return true;
        }
        return false;
    }

    /// <summary>
    /// 返回按稳定顺序排列的来源快照，供事件和协议同步使用。
    /// </summary>
    public string[] CreateSnapshot()
    {
        var snapshot = new string[_sources.Count];
        _sources.Keys.CopyTo(snapshot, 0);
        Array.Sort(snapshot, StringComparer.Ordinal);
        return snapshot;
    }

    /// <summary>
    /// 将空来源收口为统一 ID，避免无法释放的匿名暂停。
    /// </summary>
    public static string NormalizeSource(string source)
    {
        return string.IsNullOrWhiteSpace(source) ? "unknown" : source.Trim();
    }
}
