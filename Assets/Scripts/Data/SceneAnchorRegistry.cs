using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// 场景 Anchor 注册表：维护 location_id 到 SceneAnchor 的运行时映射。
/// 只负责查场景，不负责 JSON fallback。
/// </summary>
public static class SceneAnchorRegistry
{
    private static Dictionary<string, SceneAnchor> _anchors = new();
    private static bool _dirty = true;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void ResetAfterSceneLoad()
    {
        MarkDirty();
    }

    /// <summary>
    /// 标记缓存失效，下次查询时重新扫描场景。
    /// </summary>
    public static void MarkDirty()
    {
        _dirty = true;
    }

    /// <summary>
    /// 主动重建 Anchor 缓存。
    /// </summary>
    public static void Rebuild()
    {
        _anchors = new Dictionary<string, SceneAnchor>();

        var anchors = Object.FindObjectsOfType<SceneAnchor>(true);
        foreach (var anchor in anchors)
        {
            if (anchor == null || string.IsNullOrWhiteSpace(anchor.LocationId))
                continue;

            if (_anchors.ContainsKey(anchor.LocationId))
            {
                Debug.LogWarning($"[SceneAnchorRegistry] 重复的 location_id: {anchor.LocationId}，后出现的 Anchor 将覆盖前者");
            }

            _anchors[anchor.LocationId] = anchor;
        }

        _dirty = false;
        Debug.Log($"[SceneAnchorRegistry] 注册了 {_anchors.Count} 个场景 Anchor");
    }

    /// <summary>
    /// 按 ID 获取 Anchor 组件。不存在则返回 null。
    /// </summary>
    public static SceneAnchor GetAnchor(string locationId)
    {
        EnsureLoaded();
        if (string.IsNullOrWhiteSpace(locationId)) return null;
        _anchors.TryGetValue(locationId, out var anchor);
        return anchor;
    }

    /// <summary>
    /// 检查指定 ID 是否存在于场景 Anchor 中。
    /// </summary>
    public static bool HasAnchor(string locationId)
    {
        return GetAnchor(locationId) != null;
    }

    /// <summary>
    /// 获取 Anchor 对应的世界坐标（只取 XY）。
    /// </summary>
    public static Vector2? GetPosition(string locationId)
    {
        var anchor = GetAnchor(locationId);
        if (anchor == null) return null;

        var pos = anchor.transform.position;
        return new Vector2(pos.x, pos.y);
    }

    /// <summary>
    /// 获取 Anchor 区域中的采样坐标。
    /// </summary>
    public static Vector2 GetPositionWithOffset(string locationId, float fallbackRadius = 1.5f)
    {
        var anchor = GetAnchor(locationId);
        if (anchor == null) return Vector2.zero;

        return anchor.SamplePoint(fallbackRadius);
    }

    /// <summary>
    /// 获取 Anchor 区域中的多个候选坐标，供寻路系统挑选可达目标点。
    /// </summary>
    public static List<Vector2> GetCandidatePositions(string locationId, int count, float fallbackRadius = 1.5f)
    {
        var anchor = GetAnchor(locationId);
        if (anchor == null) return new List<Vector2>();

        return anchor.SampleCandidatePoints(count, fallbackRadius);
    }

    /// <summary>
    /// 从世界坐标反查最近的 Anchor。便于未来玩家位置同步到后端。
    /// </summary>
    public static bool TryResolveNearestLocation(Vector3 worldPosition, float maxDistance, out SceneAnchor nearestAnchor)
    {
        EnsureLoaded();

        nearestAnchor = null;
        float bestDistance = float.MaxValue;

        foreach (var pair in _anchors)
        {
            var anchor = pair.Value;
            if (anchor == null) continue;

            float distance = anchor.DistanceTo(new Vector2(worldPosition.x, worldPosition.y));

            if (distance <= maxDistance && distance < bestDistance)
            {
                bestDistance = distance;
                nearestAnchor = anchor;
            }
        }

        return nearestAnchor != null;
    }

    private static void EnsureLoaded()
    {
        if (_dirty)
            Rebuild();
    }
}
