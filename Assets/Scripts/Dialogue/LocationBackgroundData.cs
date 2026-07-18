using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 地点背景映射表（一个 asset 包含所有地点）。
/// 在 Project 右键 → Create → Sakurabashi → Location Background Data 创建。
/// </summary>
[CreateAssetMenu(fileName = "LocationBackgrounds", menuName = "Sakurabashi/Location Background Data")]
public class LocationBackgroundData : ScriptableObject
{
    public List<LocationBgEntry> Entries = new();

    /// <summary>根据 location_id 查背景图（按 zone 匹配: "flower_shop.counter" → "flower_shop"）</summary>
    public Sprite GetBackground(string locationId)
    {
        if (string.IsNullOrEmpty(locationId)) return null;
        string zone = locationId.Contains(".") ? locationId.Split('.')[0] : locationId;
        foreach (var e in Entries)
        {
            if (e.ZoneId == zone) return e.Background;
        }
        return Entries.Count > 0 ? Entries[0].Background : null;
    }
}

[Serializable]
public class LocationBgEntry
{
    public string ZoneId;           // "flower_shop", "bakery", ...
    public string ZoneName;         // 中文名，方便编辑
    public Sprite Background;
}
