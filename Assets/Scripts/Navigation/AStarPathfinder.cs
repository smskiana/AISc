using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 2D 网格 A* 寻路器，支持静态障碍、通行成本和带语义的传送点邻接边。
/// </summary>
public class AStarPathfinder
{
    private static readonly Vector2Int[] CardinalDirections =
    {
        new(1, 0),
        new(-1, 0),
        new(0, 1),
        new(0, -1),
    };

    private static readonly Vector2Int[] DiagonalDirections =
    {
        new(1, 1),
        new(1, -1),
        new(-1, 1),
        new(-1, -1),
    };

    private readonly NavigationGridAsset _grid;
    private readonly List<NavigationTeleportExit> _teleportBuffer = new();
    private readonly List<CellPathStep> _cellPathBuffer = new();

    public AStarPathfinder(NavigationGridAsset grid)
    {
        _grid = grid;
    }

    /// <summary>
    /// 从世界起点到世界终点查找路径，并输出兼容旧接口的世界坐标 waypoint。
    /// </summary>
    public bool TryFindPath(Vector2 startWorld, Vector2 targetWorld, List<Vector2> worldPath,
        out string failureReason)
    {
        worldPath.Clear();
        if (!TryFindNavigationPath(startWorld, targetWorld, out var navigationPath, out failureReason))
            return false;

        navigationPath.AppendWaypoints(worldPath);
        if (worldPath.Count == 0)
            worldPath.Add(targetWorld);

        return worldPath.Count > 0;
    }

    /// <summary>
    /// 从世界起点到世界终点查找路径，并保留普通行走与传送边语义。
    /// </summary>
    public bool TryFindNavigationPath(Vector2 startWorld, Vector2 targetWorld,
        out NavigationPath navigationPath, out string failureReason)
    {
        navigationPath = null;
        failureReason = null;

        if (_grid == null)
        {
            failureReason = "未配置 NavigationGridAsset。";
            return false;
        }

        if (!_grid.TryPrepare(out failureReason))
            return false;

        if (!_grid.TryWorldToCell(startWorld, out var rawStart))
        {
            failureReason = "起点不在导航网格范围内。";
            return false;
        }

        if (!_grid.TryWorldToCell(targetWorld, out var rawTarget))
        {
            failureReason = "终点不在导航网格范围内。";
            return false;
        }

        if (!_grid.TryFindNearestWalkable(rawStart, _grid.NearestWalkableSearchRadius, out var start))
        {
            failureReason = "起点附近找不到可走格。";
            return false;
        }

        if (!_grid.TryFindNearestWalkable(rawTarget, _grid.NearestWalkableSearchRadius, out var target))
        {
            failureReason = "终点附近找不到可走格。";
            return false;
        }

        if (start == target)
        {
            navigationPath = new NavigationPath(startWorld, targetWorld);
            if (Vector2.Distance(startWorld, targetWorld) > 0.01f)
                navigationPath.AddSegment(NavigationPathSegment.Walk(startWorld, targetWorld));
            return true;
        }

        bool found = FindCellPath(start, target, _cellPathBuffer);
        if (!found)
        {
            failureReason = "A* 未找到可达路径。";
            return false;
        }

        navigationPath = BuildNavigationPath(_cellPathBuffer, startWorld, targetWorld);
        return navigationPath.SegmentCount > 0;
    }

    /// <summary>
    /// 在网格坐标上执行 A* 搜索。
    /// </summary>
    private bool FindCellPath(Vector2Int start, Vector2Int target, List<CellPathStep> cellPath)
    {
        cellPath.Clear();

        int nodeCount = _grid.Width * _grid.Height;
        var records = new NodeRecord[nodeCount];
        var open = new MinHeap();

        int startIndex = _grid.CellToIndex(start);
        int targetIndex = _grid.CellToIndex(target);
        records[startIndex].Opened = true;
        records[startIndex].G = 0f;
        records[startIndex].F = Heuristic(start, target);
        records[startIndex].CameFrom = -1;
        open.Push(startIndex, records[startIndex].F);

        while (open.Count > 0)
        {
            var currentEntry = open.Pop();
            int currentIndex = currentEntry.Index;
            if (records[currentIndex].Closed) continue;

            var current = _grid.IndexToCell(currentIndex);
            records[currentIndex].Closed = true;

            if (currentIndex == targetIndex)
            {
                ReconstructPath(records, targetIndex, cellPath);
                return true;
            }

            VisitCardinalNeighbors(current, currentIndex, target, records, open);
            if (_grid.AllowDiagonal)
                VisitDiagonalNeighbors(current, currentIndex, target, records, open);
            VisitTeleportNeighbors(current, currentIndex, target, records, open);
        }

        return false;
    }

    /// <summary>
    /// 扩展上下左右四向邻居。
    /// </summary>
    private void VisitCardinalNeighbors(Vector2Int current, int currentIndex, Vector2Int target,
        NodeRecord[] records, MinHeap open)
    {
        foreach (var direction in CardinalDirections)
        {
            var next = current + direction;
            if (!_grid.IsWalkable(next)) continue;
            TryRelaxWalkNeighbor(currentIndex, next, 1f, target, records, open);
        }
    }

    /// <summary>
    /// 扩展斜向邻居，并按配置避免斜穿墙角。
    /// </summary>
    private void VisitDiagonalNeighbors(Vector2Int current, int currentIndex, Vector2Int target,
        NodeRecord[] records, MinHeap open)
    {
        foreach (var direction in DiagonalDirections)
        {
            var next = current + direction;
            if (!_grid.IsWalkable(next)) continue;

            if (_grid.PreventDiagonalCornerCutting)
            {
                var sideA = new Vector2Int(current.x + direction.x, current.y);
                var sideB = new Vector2Int(current.x, current.y + direction.y);
                if (!_grid.IsWalkable(sideA) || !_grid.IsWalkable(sideB))
                    continue;
            }

            TryRelaxWalkNeighbor(currentIndex, next, 1.41421356f, target, records, open);
        }
    }

    /// <summary>
    /// 扩展当前格可触发的传送点出口。
    /// </summary>
    private void VisitTeleportNeighbors(Vector2Int current, int currentIndex, Vector2Int target,
        NodeRecord[] records, MinHeap open)
    {
        _grid.CollectTeleportExits(current, _teleportBuffer);
        foreach (var exit in _teleportBuffer)
        {
            if (!_grid.IsWalkable(exit.Cell)) continue;
            TryRelaxTeleportNeighbor(currentIndex, exit, target, records, open);
        }
    }

    /// <summary>
    /// 更新普通行走邻居节点的最短已知路径。
    /// </summary>
    private void TryRelaxWalkNeighbor(int currentIndex, Vector2Int next, float moveCost,
        Vector2Int target, NodeRecord[] records, MinHeap open)
    {
        TryRelaxNeighbor(currentIndex, next, moveCost, target, records, open, false, default);
    }

    /// <summary>
    /// 更新传送邻居节点的最短已知路径，并记录传送边语义。
    /// </summary>
    private void TryRelaxTeleportNeighbor(int currentIndex, NavigationTeleportExit teleport,
        Vector2Int target, NodeRecord[] records, MinHeap open)
    {
        TryRelaxNeighbor(currentIndex, teleport.Cell, teleport.Cost, target, records, open, true, teleport);
    }

    /// <summary>
    /// 更新邻居节点的最短已知路径，并保存进入该节点的边类型。
    /// </summary>
    private void TryRelaxNeighbor(int currentIndex, Vector2Int next, float moveCost, Vector2Int target,
        NodeRecord[] records, MinHeap open, bool isTeleport, NavigationTeleportExit teleport)
    {
        int nextIndex = _grid.CellToIndex(next);
        if (records[nextIndex].Closed) return;

        float tentativeG = records[currentIndex].G + moveCost * _grid.GetTraversalCost(next);
        if (records[nextIndex].Opened && tentativeG >= records[nextIndex].G)
            return;

        records[nextIndex].Opened = true;
        records[nextIndex].G = tentativeG;
        records[nextIndex].F = tentativeG + Heuristic(next, target);
        records[nextIndex].CameFrom = currentIndex;
        records[nextIndex].CameFromIsTeleport = isTeleport;
        records[nextIndex].CameFromTeleport = teleport;
        open.Push(nextIndex, records[nextIndex].F);
    }

    /// <summary>
    /// 从目标节点回溯完整格子路径，并把进入该节点的边语义一并带回。
    /// </summary>
    private void ReconstructPath(NodeRecord[] records, int targetIndex, List<CellPathStep> cellPath)
    {
        int current = targetIndex;
        while (current >= 0)
        {
            cellPath.Add(new CellPathStep(
                _grid.IndexToCell(current),
                records[current].CameFromIsTeleport,
                records[current].CameFromTeleport));
            current = records[current].CameFrom;
        }

        cellPath.Reverse();
    }

    /// <summary>
    /// 将带边语义的格子路径转换为 typed navigation path。
    /// </summary>
    private NavigationPath BuildNavigationPath(List<CellPathStep> cellPath, Vector2 startWorld, Vector2 targetWorld)
    {
        var navigationPath = new NavigationPath(startWorld, targetWorld);
        if (cellPath == null || cellPath.Count == 0)
            return navigationPath;

        var currentWorld = startWorld;
        var walkRun = new List<Vector2Int> { cellPath[0].Cell };

        for (int i = 1; i < cellPath.Count; i++)
        {
            var step = cellPath[i];
            if (step.IncomingIsTeleport)
            {
                FlushWalkRun(walkRun, navigationPath, ref currentWorld, targetWorld, false);
                navigationPath.AddSegment(NavigationPathSegment.Teleport(currentWorld, step.IncomingTeleport));
                currentWorld = step.IncomingTeleport.ResolvedExitWorld;
                walkRun.Clear();
                walkRun.Add(step.Cell);
                continue;
            }

            walkRun.Add(step.Cell);
        }

        FlushWalkRun(walkRun, navigationPath, ref currentWorld, targetWorld, true);
        return navigationPath;
    }

    /// <summary>
    /// 将连续普通行走格简化成若干 Walk segment，并在最终段保留真实目标点。
    /// </summary>
    private void FlushWalkRun(List<Vector2Int> walkRun, NavigationPath navigationPath,
        ref Vector2 currentWorld, Vector2 targetWorld, bool appendTargetWorld)
    {
        if (walkRun == null || walkRun.Count == 0)
            return;

        var simplified = new List<Vector2Int>(walkRun);
        SimplifyCollinearCells(simplified);

        for (int i = 0; i < simplified.Count; i++)
        {
            var point = _grid.CellToWorldCenter(simplified[i]);
            if (i == 0 && Vector2.Distance(point, currentWorld) < _grid.CellSize * 0.5f)
                continue;

            AddWalkSegmentIfNeeded(navigationPath, ref currentWorld, point);
        }

        if (appendTargetWorld && Vector2.Distance(currentWorld, targetWorld) > _grid.CellSize * 0.25f)
            AddWalkSegmentIfNeeded(navigationPath, ref currentWorld, targetWorld);
    }

    /// <summary>
    /// 追加非零长度 Walk segment，避免产生抖动用的极短路径段。
    /// </summary>
    private void AddWalkSegmentIfNeeded(NavigationPath navigationPath, ref Vector2 currentWorld, Vector2 toWorld)
    {
        if (Vector2.Distance(currentWorld, toWorld) <= 0.01f)
            return;

        navigationPath.AddSegment(NavigationPathSegment.Walk(currentWorld, toWorld));
        currentWorld = toWorld;
    }

    /// <summary>
    /// 移除同一直线上的中间格子，减少 NPC 路径点抖动。
    /// </summary>
    private void SimplifyCollinearCells(List<Vector2Int> cells)
    {
        if (cells.Count <= 2) return;

        var simplified = new List<Vector2Int> { cells[0] };
        var previousDirection = Vector2Int.zero;
        bool hasPreviousDirection = false;

        for (int i = 1; i < cells.Count; i++)
        {
            var previousCell = cells[i - 1];
            var currentCell = cells[i];
            var delta = currentCell - previousCell;
            var direction = NormalizeCellDirection(delta);
            if (!hasPreviousDirection)
            {
                previousDirection = direction;
                hasPreviousDirection = true;
                continue;
            }

            if (direction == previousDirection) continue;

            AddCellIfDifferent(simplified, previousCell);
            previousDirection = direction;
        }

        AddCellIfDifferent(simplified, cells[^1]);
        cells.Clear();
        cells.AddRange(simplified);
    }

    /// <summary>
    /// 向简化路径追加格子，同时避免重复写入同一个端点。
    /// </summary>
    private void AddCellIfDifferent(List<Vector2Int> cells, Vector2Int cell)
    {
        if (cells.Count == 0 || cells[^1] != cell)
            cells.Add(cell);
    }

    /// <summary>
    /// 根据是否允许斜向移动选择合适启发函数。
    /// </summary>
    private float Heuristic(Vector2Int from, Vector2Int to)
    {
        int dx = Mathf.Abs(from.x - to.x);
        int dy = Mathf.Abs(from.y - to.y);

        if (!_grid.AllowDiagonal)
            return dx + dy;

        int min = Mathf.Min(dx, dy);
        int max = Mathf.Max(dx, dy);
        return 1.41421356f * min + (max - min);
    }

    /// <summary>
    /// 把任意格子差值压成方向向量，便于判断是否共线。
    /// </summary>
    private Vector2Int NormalizeCellDirection(Vector2Int delta)
    {
        return new Vector2Int(
            delta.x == 0 ? 0 : delta.x > 0 ? 1 : -1,
            delta.y == 0 ? 0 : delta.y > 0 ? 1 : -1);
    }

    private struct NodeRecord
    {
        public bool Opened;
        public bool Closed;
        public float G;
        public float F;
        public int CameFrom;
        public bool CameFromIsTeleport;
        public NavigationTeleportExit CameFromTeleport;
    }

    private readonly struct CellPathStep
    {
        public readonly Vector2Int Cell;
        public readonly bool IncomingIsTeleport;
        public readonly NavigationTeleportExit IncomingTeleport;

        public CellPathStep(Vector2Int cell, bool incomingIsTeleport, NavigationTeleportExit incomingTeleport)
        {
            Cell = cell;
            IncomingIsTeleport = incomingIsTeleport;
            IncomingTeleport = incomingTeleport;
        }
    }

    private readonly struct HeapEntry
    {
        public readonly int Index;
        public readonly float Priority;

        public HeapEntry(int index, float priority)
        {
            Index = index;
            Priority = priority;
        }
    }

    /// <summary>
    /// A* 使用的小顶堆，允许重复入队，出队时由 Closed 标记过滤旧项。
    /// </summary>
    private class MinHeap
    {
        private readonly List<HeapEntry> _items = new();

        public int Count => _items.Count;

        /// <summary>
        /// 插入一个待访问节点。
        /// </summary>
        public void Push(int index, float priority)
        {
            _items.Add(new HeapEntry(index, priority));
            SiftUp(_items.Count - 1);
        }

        /// <summary>
        /// 弹出优先级最低的节点。
        /// </summary>
        public HeapEntry Pop()
        {
            var root = _items[0];
            var last = _items[^1];
            _items.RemoveAt(_items.Count - 1);
            if (_items.Count > 0)
            {
                _items[0] = last;
                SiftDown(0);
            }

            return root;
        }

        /// <summary>
        /// 将新插入项上浮到正确位置。
        /// </summary>
        private void SiftUp(int index)
        {
            while (index > 0)
            {
                int parent = (index - 1) / 2;
                if (_items[parent].Priority <= _items[index].Priority) break;
                Swap(parent, index);
                index = parent;
            }
        }

        /// <summary>
        /// 将堆顶项下沉到正确位置。
        /// </summary>
        private void SiftDown(int index)
        {
            while (true)
            {
                int left = index * 2 + 1;
                int right = left + 1;
                int smallest = index;

                if (left < _items.Count && _items[left].Priority < _items[smallest].Priority)
                    smallest = left;
                if (right < _items.Count && _items[right].Priority < _items[smallest].Priority)
                    smallest = right;

                if (smallest == index) break;
                Swap(index, smallest);
                index = smallest;
            }
        }

        /// <summary>
        /// 交换堆中两个元素。
        /// </summary>
        private void Swap(int a, int b)
        {
            (_items[a], _items[b]) = (_items[b], _items[a]);
        }
    }
}
