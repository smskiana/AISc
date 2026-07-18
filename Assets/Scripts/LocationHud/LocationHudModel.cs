using System;
using System.Collections.Generic;

/// <summary>
/// 保存玩家当前位置，并通过统一映射解析大区域显示名。
/// </summary>
public sealed class LocationHudModel
{
    private static readonly Dictionary<string, string> DisplayNames = new Dictionary<string, string>(StringComparer.Ordinal)
    {
        { "street", "樱桥通" },
        { "player_cafe", "喫茶店" },
        { "flower_shop", "花店" },
        { "bakery", "面包店" },
        { "bookstore", "旧书店" },
        { "wagashi", "和果子店" },
        { "police_box", "派出所" },
        { "park", "公园" },
        { "riverside", "河畔" },
    };

    public string LocationId { get; private set; } = string.Empty;
    public string DisplayName { get; private set; } = "未知";

    /// <summary>
    /// 更新内部地点 ID，并解析第一个点号前的大区域名称。
    /// </summary>
    public void SetLocation(string locationId)
    {
        LocationId = locationId ?? string.Empty;
        string regionId = LocationId;
        int separatorIndex = regionId.IndexOf('.');
        if (separatorIndex >= 0)
            regionId = regionId.Substring(0, separatorIndex);

        DisplayName = DisplayNames.TryGetValue(regionId, out string displayName)
            ? displayName
            : "未知";
    }
}
