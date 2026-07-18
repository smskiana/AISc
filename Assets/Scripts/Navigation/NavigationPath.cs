using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 导航路径段类型，用于区分普通行走和传送边。
/// </summary>
public enum NavigationPathSegmentType
{
    Walk,
    Teleport,
}

/// <summary>
/// 一段具有明确语义的导航路径。
/// </summary>
public readonly struct NavigationPathSegment
{
    public readonly NavigationPathSegmentType Type;
    public readonly Vector2 FromWorld;
    public readonly Vector2 ToWorld;
    public readonly string LinkId;
    public readonly Vector2 EntranceWorld;
    public readonly Vector2 ExitWorld;
    public readonly Vector2 ResolvedExitWorld;
    public readonly bool IsReverse;

    /// <summary>
    /// 创建一段普通行走路径。
    /// </summary>
    public static NavigationPathSegment Walk(Vector2 fromWorld, Vector2 toWorld)
    {
        return new NavigationPathSegment(
            NavigationPathSegmentType.Walk,
            fromWorld,
            toWorld,
            null,
            default,
            default,
            default,
            false);
    }

    /// <summary>
    /// 创建一段传送路径，保留 link 配置和解析后的出口落点。
    /// </summary>
    public static NavigationPathSegment Teleport(Vector2 fromWorld, NavigationTeleportExit teleport)
    {
        return new NavigationPathSegment(
            NavigationPathSegmentType.Teleport,
            fromWorld,
            teleport.ResolvedExitWorld,
            teleport.LinkId,
            teleport.EntranceWorld,
            teleport.ExitWorld,
            teleport.ResolvedExitWorld,
            teleport.IsReverse);
    }

    private NavigationPathSegment(NavigationPathSegmentType type, Vector2 fromWorld, Vector2 toWorld,
        string linkId, Vector2 entranceWorld, Vector2 exitWorld, Vector2 resolvedExitWorld, bool isReverse)
    {
        Type = type;
        FromWorld = fromWorld;
        ToWorld = toWorld;
        LinkId = linkId;
        EntranceWorld = entranceWorld;
        ExitWorld = exitWorld;
        ResolvedExitWorld = resolvedExitWorld;
        IsReverse = isReverse;
    }
}

/// <summary>
/// A* 输出的 typed path，路径段会保留普通行走与传送语义。
/// </summary>
public class NavigationPath
{
    private readonly List<NavigationPathSegment> _segments = new();

    public IReadOnlyList<NavigationPathSegment> Segments => _segments;
    public Vector2 StartWorld { get; }
    public Vector2 TargetWorld { get; }

    public int SegmentCount => _segments.Count;

    public NavigationPath(Vector2 startWorld, Vector2 targetWorld)
    {
        StartWorld = startWorld;
        TargetWorld = targetWorld;
    }

    /// <summary>
    /// 追加路径段，调用方负责保证路径段顺序连续。
    /// </summary>
    public void AddSegment(NavigationPathSegment segment)
    {
        _segments.Add(segment);
    }

    /// <summary>
    /// 展平成旧 waypoint 列表，供兼容接口和调试工具使用。
    /// </summary>
    public void AppendWaypoints(List<Vector2> worldPath)
    {
        if (worldPath == null)
            return;

        foreach (var segment in _segments)
        {
            worldPath.Add(segment.Type == NavigationPathSegmentType.Teleport
                ? segment.ResolvedExitWorld
                : segment.ToWorld);
        }
    }
}
