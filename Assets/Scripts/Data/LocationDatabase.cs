using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// location_id → Unity 世界坐标 映射表。
/// 运行时优先使用场景中的 SceneAnchor，查不到时再回退到
/// Resources/Config/location_positions.json。
///
/// 使用方式:
///   LocationDatabase.Load();
///   Vector2? pos = LocationDatabase.GetPosition("flower_shop.doorway");
///   Vector2 randPos = LocationDatabase.GetPositionWithOffset("flower_shop.doorway", 1.5f);
/// </summary>
public static class LocationDatabase
{
    private static Dictionary<string, Vector2> _fallbackPositions;
    private static bool _fallbackLoaded;

    // ── JSON 结构（数组格式，兼容 Unity JsonUtility）──
    [Serializable]
    private class LocationEntry
    {
        public string id;
        public float x;
        public float y;
    }

    [Serializable]
    private class LocationList
    {
        public LocationEntry[] locations;
    }

    /// <summary>
    /// 初始化位置来源。会主动重建场景 Anchor，并加载 JSON fallback。
    /// </summary>
    public static void Load()
    {
        SceneAnchorRegistry.Rebuild();
        EnsureFallbackLoaded();
    }

    /// <summary>
    /// 获取 location_id 对应的世界坐标。
    /// 优先场景 Anchor，其次 JSON fallback。
    /// </summary>
    /// <returns>坐标，若不存在返回 null</returns>
    public static Vector2? GetPosition(string locationId)
    {
        var anchorPos = SceneAnchorRegistry.GetPosition(locationId);
        if (anchorPos != null)
            return anchorPos;

        EnsureFallbackLoaded();

        if (_fallbackPositions.TryGetValue(locationId, out var fallbackPos))
            return fallbackPos;

        Debug.LogWarning($"[LocationDB] 未找到位置: {locationId}");
        return null;
    }

    /// <summary>
    /// 获取带随机偏移的坐标（避免多个 NPC 站在同一像素）。
    /// 优先场景 Anchor 区域采样，其次 JSON fallback。
    /// </summary>
    /// <param name="locationId">位置 ID</param>
    /// <param name="radius">随机偏移半径（默认 1.5）</param>
    /// <returns>坐标 + 圆形随机偏移；不存在则返回 Vector2.zero</returns>
    public static Vector2 GetPositionWithOffset(string locationId, float radius = 1.5f)
    {
        if (SceneAnchorRegistry.HasAnchor(locationId))
            return SceneAnchorRegistry.GetPositionWithOffset(locationId, radius);

        var pos = GetPosition(locationId);
        if (pos == null) return Vector2.zero;

        var offset = UnityEngine.Random.insideUnitCircle * radius;
        return pos.Value + offset;
    }

    /// <summary>
    /// 获取多个目标候选点；场景 Anchor 会从区域组合中采样，fallback JSON 使用圆形随机偏移。
    /// </summary>
    public static List<Vector2> GetCandidatePositions(string locationId, int count = 12, float radius = 1.5f)
    {
        count = Mathf.Max(1, count);

        if (SceneAnchorRegistry.HasAnchor(locationId))
            return SceneAnchorRegistry.GetCandidatePositions(locationId, count, radius);

        var results = new List<Vector2>(count);
        var pos = GetPosition(locationId);
        if (pos == null) return results;

        results.Add(pos.Value);
        while (results.Count < count)
            results.Add(pos.Value + UnityEngine.Random.insideUnitCircle * radius);

        return results;
    }

    /// <summary>
    /// 检查位置 ID 是否存在于数据库中。
    /// </summary>
    public static bool HasPosition(string locationId)
    {
        if (SceneAnchorRegistry.HasAnchor(locationId))
            return true;

        EnsureFallbackLoaded();
        return _fallbackPositions.ContainsKey(locationId);
    }

    /// <summary>
    /// 从 Resources 加载 fallback JSON。重复调用安全（幂等）。
    /// </summary>
    private static void EnsureFallbackLoaded()
    {
        if (_fallbackLoaded) return;

        _fallbackPositions = new Dictionary<string, Vector2>();

        var asset = Resources.Load<TextAsset>("Config/location_positions");
        if (asset == null)
        {
            Debug.LogWarning("[LocationDB] location_positions.json 未找到，使用空表");
            _fallbackLoaded = true;
            return;
        }

        try
        {
            var list = JsonUtility.FromJson<LocationList>(asset.text);
            if (list?.locations != null)
            {
                foreach (var entry in list.locations)
                {
                    _fallbackPositions[entry.id] = new Vector2(entry.x, entry.y);
                }
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"[LocationDB] JSON 解析失败: {e.Message}");
        }

        _fallbackLoaded = true;
        Debug.Log($"[LocationDB] 加载了 {_fallbackPositions.Count} 个 fallback 位置坐标");
    }
}
