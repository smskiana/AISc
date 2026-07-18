using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 基于 NavigationGridAsset 的 NPC A* 移动实现，只负责执行 typed navigation path。
/// </summary>
public class AStarMovementProvider : IMovementProvider
{
    private const int LocationCandidateCount = 16;
    private const float LocationCandidateRadius = 1.5f;

    private readonly NavigationGridAsset _navigationGrid;
    private readonly AStarPathfinder _pathfinder;
    private readonly LerpMovementProvider _fallbackMovement = new();
    private readonly Dictionary<Transform, Coroutine> _runningMoves = new();
    private readonly Dictionary<Transform, Action<MovementResult>> _runningCallbacks = new();

    public AStarMovementProvider(NavigationGridAsset navigationGrid)
    {
        _navigationGrid = navigationGrid;
        _pathfinder = navigationGrid != null ? new AStarPathfinder(navigationGrid) : null;
    }

    /// <summary>
    /// 计算 A* typed path 并沿路径段移动；失败时回退为旧直线移动。
    /// </summary>
    public void MoveTo(Transform transform, Vector2 target, float speed, Action<MovementResult> onComplete)
    {
        if (transform == null)
        {
            onComplete?.Invoke(MovementResult.Failed);
            return;
        }

        var runner = transform.GetComponent<MonoBehaviour>();
        if (runner == null)
        {
            Debug.LogWarning("[AStarMove] 需要 MonoBehaviour 来运行 Coroutine");
            onComplete?.Invoke(MovementResult.Failed);
            return;
        }

        Stop(transform);

        if (_pathfinder == null || _navigationGrid == null)
        {
            NavigationDebugLog.Log(transform,
                $"直线回退 MoveTo target={NavigationDebugLog.FormatVector(target)}，原因=未配置导航网格");
            _fallbackMovement.MoveTo(transform, target, speed, onComplete);
            return;
        }

        if (!_pathfinder.TryFindNavigationPath(transform.position, target, out var path, out var failureReason))
        {
            Debug.LogWarning($"[AStarMove] 路径失败，回退直线移动: {failureReason}");
            _fallbackMovement.MoveTo(transform, target, speed, onComplete);
            return;
        }

        NavigationDebugLog.LogPathSummary(transform,
            $"MoveTo target={NavigationDebugLog.FormatVector(target)}",
            path);
        _runningCallbacks[transform] = onComplete;
        var coroutine = runner.StartCoroutine(MoveAlongPath(transform, path, speed));
        _runningMoves[transform] = coroutine;
    }

    /// <summary>
    /// 从 location_id 的多个区域候选点中挑选第一条 A* 可达 typed path。
    /// </summary>
    public void MoveToLocation(Transform transform, string locationId, float speed, Action<MovementResult> onComplete)
    {
        if (transform == null)
        {
            onComplete?.Invoke(MovementResult.Failed);
            return;
        }

        var runner = transform.GetComponent<MonoBehaviour>();
        if (runner == null)
        {
            Debug.LogWarning("[AStarMove] 需要 MonoBehaviour 来运行 Coroutine");
            onComplete?.Invoke(MovementResult.Failed);
            return;
        }

        Stop(transform);

        if (_pathfinder == null || _navigationGrid == null)
        {
            NavigationDebugLog.Log(transform,
                $"直线回退 MoveToLocation location={locationId}，原因=未配置导航网格");
            _fallbackMovement.MoveToLocation(transform, locationId, speed, onComplete);
            return;
        }

        NavigationDebugLog.Log(transform,
            $"请求移动 location={locationId} start={NavigationDebugLog.FormatVector(transform.position)} speed={speed:F2}");
        SnapStartToNearestWalkable(transform);

        var candidates = LocationDatabase.GetCandidatePositions(locationId, LocationCandidateCount, LocationCandidateRadius);
        NavigationDebugLog.LogLocationCandidateBatch(transform, locationId, candidates);
        string lastFailure = "没有可用候选点。";

        for (int i = 0; i < candidates.Count; i++)
        {
            var candidate = candidates[i];
            if (TryFindReachablePath(transform.position, candidate, out var path, out var failureReason, out var probe))
            {
                NavigationDebugLog.LogLocationCandidateEvaluation(transform, locationId, i,
                    candidate, probe.HasRawCell, probe.RawCell, probe.HasResolvedTarget,
                    probe.ResolvedCell, probe.ResolvedTarget, true, failureReason, path);
                NavigationDebugLog.LogSelectedLocationCandidate(transform, locationId, i,
                    candidate, probe.ResolvedTarget, path);
                NavigationDebugLog.LogPathSummary(transform, $"MoveToLocation location={locationId}", path);
                _runningCallbacks[transform] = onComplete;
                var coroutine = runner.StartCoroutine(MoveAlongPath(transform, path, speed));
                _runningMoves[transform] = coroutine;
                return;
            }

            NavigationDebugLog.LogLocationCandidateEvaluation(transform, locationId, i,
                candidate, probe.HasRawCell, probe.RawCell, probe.HasResolvedTarget,
                probe.ResolvedCell, probe.ResolvedTarget, false, failureReason, null);
            lastFailure = failureReason;
        }

        Debug.LogWarning($"[AStarMove] location_id={locationId} 所有候选点均不可达，已取消本次移动: {lastFailure}");
        onComplete?.Invoke(MovementResult.Failed);
    }

    /// <summary>
    /// 停止指定 Transform 的 A* 移动。
    /// </summary>
    public void Stop(Transform transform)
    {
        if (transform == null) return;

        var runner = transform.GetComponent<MonoBehaviour>();
        if (runner != null && _runningMoves.TryGetValue(transform, out var coroutine) && coroutine != null)
        {
            runner.StopCoroutine(coroutine);
        }

        CompleteMove(transform, MovementResult.Cancelled);
        _fallbackMovement.Stop(transform);
    }

    /// <summary>
    /// 将候选点修正到最近可走格后尝试寻路，避免最终 waypoint 落在障碍物内。
    /// </summary>
    private bool TryFindReachablePath(Vector2 startWorld, Vector2 requestedTarget,
        out NavigationPath path, out string failureReason, out CandidatePathProbe probe)
    {
        path = null;
        probe = CandidatePathProbe.Empty;

        if (!_navigationGrid.TryPrepare(out failureReason))
            return false;

        if (!_navigationGrid.TryWorldToCell(requestedTarget, out var rawTarget))
        {
            failureReason = "候选点不在导航网格范围内。";
            return false;
        }

        probe = CandidatePathProbe.WithRawCell(rawTarget);
        if (!_navigationGrid.TryFindNearestWalkable(rawTarget, _navigationGrid.NearestWalkableSearchRadius, out var targetCell))
        {
            failureReason = "候选点附近找不到可走格。";
            return false;
        }

        var reachableTarget = _navigationGrid.CellToWorldCenter(targetCell);
        probe = CandidatePathProbe.WithResolvedTarget(rawTarget, targetCell, reachableTarget);
        return _pathfinder.TryFindNavigationPath(startWorld, reachableTarget, out path, out failureReason);
    }

    /// <summary>
    /// 若 NPC 当前站在不可走格上，先瞬移吸附到最近可走格，避免把起点修正动画成一段虚空直线。
    /// </summary>
    private void SnapStartToNearestWalkable(Transform transform)
    {
        if (transform == null || _navigationGrid == null)
            return;

        if (!_navigationGrid.TryPrepare(out _))
            return;

        Vector2 current = transform.position;
        if (!_navigationGrid.TryWorldToCell(current, out var rawStart))
            return;

        if (_navigationGrid.IsWalkable(rawStart))
            return;

        if (!_navigationGrid.TryFindNearestWalkable(rawStart, _navigationGrid.NearestWalkableSearchRadius, out var startCell))
        {
            NavigationDebugLog.Log(transform,
                $"起点不可走且附近无可走格 current={NavigationDebugLog.FormatVector(current)} rawCell={rawStart} searchRadius={_navigationGrid.NearestWalkableSearchRadius}");
            return;
        }

        var snapped = _navigationGrid.CellToWorldCenter(startCell);
        transform.position = new Vector3(snapped.x, snapped.y, transform.position.z);
        NavigationDebugLog.Log(transform,
            $"起点吸附 current={NavigationDebugLog.FormatVector(current)} rawCell={rawStart} -> walkableCell={startCell} world={NavigationDebugLog.FormatVector(snapped)}");
    }

    /// <summary>
    /// 按 typed path 顺序执行移动段，遇到传送段直接放置到解析后的出口可走格。
    /// </summary>
    private IEnumerator MoveAlongPath(Transform transform, NavigationPath path, float speed)
    {
        speed = Mathf.Max(0.01f, speed);

        foreach (var segment in path.Segments)
        {
            if (segment.Type == NavigationPathSegmentType.Teleport)
            {
                float entranceDistance = Vector2.Distance(transform.position, segment.EntranceWorld);
                float exitSnapDistance = Vector2.Distance(segment.ExitWorld, segment.ResolvedExitWorld);
                NavigationDebugLog.Log(transform,
                    $"执行传送段 link={segment.LinkId} actualFrom={NavigationDebugLog.FormatVector(transform.position)} entrance={NavigationDebugLog.FormatVector(segment.EntranceWorld)} entranceDistance={entranceDistance:F3} configuredExit={NavigationDebugLog.FormatVector(segment.ExitWorld)} resolvedExit={NavigationDebugLog.FormatVector(segment.ResolvedExitWorld)} exitSnapDistance={exitSnapDistance:F3} reverse={segment.IsReverse}");
                transform.position = new Vector3(segment.ResolvedExitWorld.x, segment.ResolvedExitWorld.y, transform.position.z);
                yield return null;
                continue;
            }

            yield return MoveWalkSegment(transform, segment.ToWorld, speed);
        }

        NavigationDebugLog.Log(transform, $"移动完成 pos={NavigationDebugLog.FormatVector(transform.position)}");
        CompleteMove(transform, MovementResult.Succeeded);
    }

    /// <summary>
    /// 移除运行记录并发送一次移动结果回调。
    /// </summary>
    private void CompleteMove(Transform transform, MovementResult result)
    {
        _runningMoves.Remove(transform);

        if (!_runningCallbacks.TryGetValue(transform, out var callback))
            return;

        _runningCallbacks.Remove(transform);
        callback?.Invoke(result);
    }

    /// <summary>
    /// 执行一段普通行走路径，遇到对话或气泡移动锁时暂停推进。
    /// </summary>
    private IEnumerator MoveWalkSegment(Transform transform, Vector2 target, float speed)
    {
        Vector3 end = new Vector3(target.x, target.y, transform.position.z);
        var segmentDistance = Vector2.Distance(transform.position, target);
        if (segmentDistance >= NavigationDebugLog.LongSegmentLogDistance)
        {
            NavigationDebugLog.Log(transform,
                $"执行长路径段 from={NavigationDebugLog.FormatVector(transform.position)} to={NavigationDebugLog.FormatVector(target)} distance={segmentDistance:F2}");
        }

        while (Vector3.Distance(transform.position, end) > 0.01f)
        {
            var gm = GameManager.Instance;
            var npc = transform.GetComponent<NpcEntity>();
            if ((gm != null && gm.IsDialogueActive) || (npc != null && npc.IsMotionLocked))
            {
                yield return null;
                continue;
            }

            transform.position = Vector3.MoveTowards(transform.position, end, speed * Time.deltaTime);
            yield return null;
        }

        transform.position = end;
    }

    private readonly struct CandidatePathProbe
    {
        public readonly bool HasRawCell;
        public readonly Vector2Int RawCell;
        public readonly bool HasResolvedTarget;
        public readonly Vector2Int ResolvedCell;
        public readonly Vector2 ResolvedTarget;

        private CandidatePathProbe(bool hasRawCell, Vector2Int rawCell,
            bool hasResolvedTarget, Vector2Int resolvedCell, Vector2 resolvedTarget)
        {
            HasRawCell = hasRawCell;
            RawCell = rawCell;
            HasResolvedTarget = hasResolvedTarget;
            ResolvedCell = resolvedCell;
            ResolvedTarget = resolvedTarget;
        }

        public static CandidatePathProbe Empty => new(false, default, false, default, default);

        /// <summary>
        /// 创建只解析到原始导航格的候选诊断结果。
        /// </summary>
        public static CandidatePathProbe WithRawCell(Vector2Int rawCell)
        {
            return new CandidatePathProbe(true, rawCell, false, default, default);
        }

        /// <summary>
        /// 创建已解析到最终可走目标格的候选诊断结果。
        /// </summary>
        public static CandidatePathProbe WithResolvedTarget(Vector2Int rawCell, Vector2Int resolvedCell,
            Vector2 resolvedTarget)
        {
            return new CandidatePathProbe(true, rawCell, true, resolvedCell, resolvedTarget);
        }
    }
}
