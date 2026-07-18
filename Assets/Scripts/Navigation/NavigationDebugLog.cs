using System.Text;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 导航诊断日志工具，集中输出 NPC 身份、路径摘要和关键异常段。
/// </summary>
public static class NavigationDebugLog
{
    public static bool Enabled = true;
    public const float LongSegmentLogDistance = 1.5f;
    private const float CandidateUniquePrecision = 0.01f;
    private const int MaxCandidateSamples = 16;
    private static readonly Dictionary<string, Vector2> LastSelectedCandidateByEntityAndLocation = new();

    /// <summary>
    /// 输出单条导航诊断日志，统一附带 NPC 身份。
    /// </summary>
    public static void Log(Transform transform, string message)
    {
        if (!Enabled)
            return;

        Debug.Log($"[AStarMove:{GetEntityLabel(transform)}] {message}");
    }

    /// <summary>
    /// 输出 typed path 摘要，便于确认传送边是否由 A* 明确产出。
    /// </summary>
    public static void LogPathSummary(Transform transform, string label, NavigationPath path)
    {
        if (!Enabled)
            return;

        var sb = new StringBuilder();
        sb.Append($"[AStarMove:{GetEntityLabel(transform)}] 路径摘要 {label} start={FormatVector(path?.StartWorld ?? Vector2.zero)} count={path?.SegmentCount ?? 0}");

        if (path != null)
        {
            var segments = path.Segments;
            for (int i = 0; i < segments.Count; i++)
            {
                var segment = segments[i];
                if (segment.Type == NavigationPathSegmentType.Teleport)
                {
                    float entranceDistance = Vector2.Distance(segment.FromWorld, segment.EntranceWorld);
                    float exitSnapDistance = Vector2.Distance(segment.ExitWorld, segment.ResolvedExitWorld);
                    sb.Append($"\n  #{i} TELEPORT link={segment.LinkId} enterFrom={FormatVector(segment.FromWorld)} entrance={FormatVector(segment.EntranceWorld)} entranceDistance={entranceDistance:F3} configuredExit={FormatVector(segment.ExitWorld)} resolvedExit={FormatVector(segment.ResolvedExitWorld)} exitSnapDistance={exitSnapDistance:F3} reverse={segment.IsReverse}");
                    continue;
                }

                float distance = Vector2.Distance(segment.FromWorld, segment.ToWorld);
                string kind = distance >= LongSegmentLogDistance ? $"long {distance:F2}" : $"walk {distance:F2}";
                sb.Append($"\n  #{i} {FormatVector(segment.ToWorld)} [{kind}]");
            }
        }

        Debug.Log(sb.ToString());
    }

    /// <summary>
    /// 输出一次 MoveToLocation 请求生成的候选点批次，用于检查 SceneAnchor 采样是否真的随机。
    /// </summary>
    public static void LogLocationCandidateBatch(Transform transform, string locationId, IReadOnlyList<Vector2> candidates)
    {
        if (!Enabled)
            return;

        int count = candidates?.Count ?? 0;
        if (count <= 0)
        {
            Log(transform, $"候选点批次 location={locationId} count=0");
            return;
        }

        var unique = new HashSet<Vector2Int>();
        var min = candidates[0];
        var max = candidates[0];
        var samples = new StringBuilder();

        for (int i = 0; i < count; i++)
        {
            var candidate = candidates[i];
            unique.Add(new Vector2Int(
                Mathf.RoundToInt(candidate.x / CandidateUniquePrecision),
                Mathf.RoundToInt(candidate.y / CandidateUniquePrecision)));
            min = Vector2.Min(min, candidate);
            max = Vector2.Max(max, candidate);

            if (i < MaxCandidateSamples)
            {
                if (samples.Length > 0)
                    samples.Append(" ");
                samples.Append($"#{i}{FormatVector(candidate)}");
            }
        }

        Log(transform,
            $"候选点批次 location={locationId} count={count} unique≈{unique.Count} bbox={FormatVector(min)}..{FormatVector(max)} samples={samples}");
    }

    /// <summary>
    /// 输出单个候选点从 raw 坐标到可走格修正和寻路结果的诊断信息。
    /// </summary>
    public static void LogLocationCandidateEvaluation(Transform transform, string locationId, int index,
        Vector2 rawCandidate, bool hasRawCell, Vector2Int rawCell, bool hasResolvedTarget,
        Vector2Int resolvedCell, Vector2 resolvedTarget, bool success, string failureReason,
        NavigationPath path)
    {
        if (!Enabled)
            return;

        string rawCellText = hasRawCell ? FormatCell(rawCell) : "out_of_grid";
        string resolvedText = hasResolvedTarget
            ? $"{FormatCell(resolvedCell)} world={FormatVector(resolvedTarget)} rawDelta={Vector2.Distance(rawCandidate, resolvedTarget):F3}"
            : "none";
        int teleportCount = CountTeleportSegments(path);
        string result = success
            ? $"success segments={path?.SegmentCount ?? 0} teleports={teleportCount}"
            : $"failed reason={failureReason}";

        Log(transform,
            $"候选评估 location={locationId} candidate#{index} raw={FormatVector(rawCandidate)} rawCell={rawCellText} resolved={resolvedText} {result}");
    }

    /// <summary>
    /// 输出最终选中的 location 候选点，并和同 NPC 上一次同 location 选点做距离对比。
    /// </summary>
    public static void LogSelectedLocationCandidate(Transform transform, string locationId, int index,
        Vector2 rawCandidate, Vector2 resolvedTarget, NavigationPath path)
    {
        if (!Enabled)
            return;

        string key = $"{GetEntityLabel(transform)}|{locationId}";
        bool hasPrevious = LastSelectedCandidateByEntityAndLocation.TryGetValue(key, out var previous);
        float previousDistance = hasPrevious ? Vector2.Distance(previous, rawCandidate) : 0f;
        LastSelectedCandidateByEntityAndLocation[key] = rawCandidate;

        string previousText = hasPrevious
            ? $" previousRaw={FormatVector(previous)} previousDelta={previousDistance:F3}"
            : " previousRaw=none";
        Log(transform,
            $"选中候选 location={locationId} candidate#{index} raw={FormatVector(rawCandidate)} resolved={FormatVector(resolvedTarget)} teleports={CountTeleportSegments(path)}{previousText}");
    }

    /// <summary>
    /// 生成日志中使用的 NPC 标签。
    /// </summary>
    public static string GetEntityLabel(Transform transform)
    {
        if (transform == null)
            return "null";

        var npc = transform.GetComponent<NpcEntity>();
        if (npc == null)
            return transform.name;

        return $"{npc.NpcId}/{npc.NpcName}";
    }

    /// <summary>
    /// 用较短格式输出二维坐标，避免 Console 日志过长。
    /// </summary>
    public static string FormatVector(Vector2 value)
    {
        return $"({value.x:F3},{value.y:F3})";
    }

    /// <summary>
    /// 用短格式输出导航格坐标。
    /// </summary>
    public static string FormatCell(Vector2Int value)
    {
        return $"[{value.x},{value.y}]";
    }

    /// <summary>
    /// 统计路径中明确的传送段数量。
    /// </summary>
    private static int CountTeleportSegments(NavigationPath path)
    {
        if (path == null)
            return 0;

        int count = 0;
        foreach (var segment in path.Segments)
        {
            if (segment.Type == NavigationPathSegmentType.Teleport)
                count++;
        }

        return count;
    }
}
