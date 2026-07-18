using System;
using System.Collections.Generic;
using UnityEngine;

#if ODIN_INSPECTOR
using Sirenix.OdinInspector;
#endif

/// <summary>
/// 2D 静态导航网格资产，可从遮罩 Sprite 或编辑器烘焙数据读取可走格与通行成本。
/// </summary>
[CreateAssetMenu(fileName = "NavGrid_Main", menuName = "SakurabashiDoori/Navigation/Grid Asset")]
public class NavigationGridAsset : ScriptableObject
{
#if ODIN_INSPECTOR
    [TitleGroup("NPC A* 导航网格")]
    [BoxGroup("NPC A* 导航网格/来源")]
    [EnumToggleButtons]
    [LabelText("数据来源")]
#endif
    [Header("Source")]
    [SerializeField] private NavigationGridSourceMode _sourceMode = NavigationGridSourceMode.BakedCells;

#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/网格")]
    [ReadOnly]
    [LabelText("世界原点")]
#endif
    [Header("World Grid")]
    [SerializeField] private Vector2 _worldOrigin = Vector2.zero;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/网格")]
    [ReadOnly]
    [LabelText("宽")]
#endif
    [SerializeField] private int _width = 128;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/网格")]
    [ReadOnly]
    [LabelText("高")]
#endif
    [SerializeField] private int _height = 72;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/网格")]
    [ReadOnly]
    [LabelText("格子尺寸")]
#endif
    [SerializeField] private float _cellSize = 0.25f;

#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/遮罩兼容模式")]
    [ShowIf(nameof(IsMaskSpriteMode))]
    [LabelText("可走遮罩 Sprite")]
#endif
    [Header("Mask Sprite")]
    [SerializeField] private Sprite _walkableMaskSprite;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/遮罩兼容模式")]
    [ShowIf(nameof(IsMaskSpriteMode))]
    [LabelText("亮色为可走")]
#endif
    [SerializeField] private bool _lightPixelsAreWalkable = true;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/遮罩兼容模式")]
    [ShowIf(nameof(IsMaskSpriteMode))]
    [LabelText("透明为可走")]
#endif
    [SerializeField] private bool _transparentPixelsAreWalkable;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/遮罩兼容模式")]
    [ShowIf(nameof(IsMaskSpriteMode))]
    [LabelText("亮度阈值")]
#endif
    [SerializeField, Range(0f, 1f)] private float _walkableThreshold = 0.5f;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/遮罩兼容模式")]
    [ShowIf(nameof(IsMaskSpriteMode))]
    [LabelText("Alpha 阈值")]
#endif
    [SerializeField, Range(0f, 1f)] private float _alphaThreshold = 0.1f;

    [Header("Baked Cells")]
    [SerializeField, UnityEngine.HideInInspector] private List<bool> _bakedWalkable = new();
    [SerializeField, UnityEngine.HideInInspector] private List<float> _bakedTraversalCost = new();
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/烘焙结果")]
    [ReadOnly]
    [LabelText("烘焙摘要")]
#endif
    [SerializeField] private string _bakedSourceSummary;

#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/移动")]
    [LabelText("允许斜向")]
#endif
    [Header("Movement")]
    [SerializeField] private bool _allowDiagonal = true;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/移动")]
    [LabelText("禁止斜穿墙角")]
#endif
    [SerializeField] private bool _preventDiagonalCornerCutting = true;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/移动")]
    [LabelText("最近可走格搜索半径")]
    [MinValue(0)]
#endif
    [SerializeField] private int _nearestWalkableSearchRadius = 8;

#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/传送点")]
    [ListDrawerSettings(DefaultExpandedState = true, DraggableItems = true)]
#endif
    [Header("Teleport Links")]
    [SerializeField] private List<NavigationTeleportLink> _teleportLinks = new();

#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航网格/烘焙结果")]
    [ShowInInspector]
    [ReadOnly]
    [LabelText("烘焙格子数")]
    private int BakedCellCount => _bakedWalkable?.Count ?? 0;

    [BoxGroup("NPC A* 导航网格/烘焙结果")]
    [ShowInInspector]
    [ReadOnly]
    [LabelText("可走格子数")]
    private int BakedWalkableCount => GetBakedWalkableCellCount();

    [BoxGroup("NPC A* 导航网格/烘焙结果")]
    [ShowInInspector]
    [ReadOnly]
    [LabelText("网格尺寸")]
    private string GridSizeSummary => $"{_width} x {_height} ({_width * _height} cells)";
#endif

    private bool[] _walkableCache;
    private float[] _costCache;
    private bool _cacheBuilt;
    private string _lastBuildError;

    public NavigationGridSourceMode SourceMode => _sourceMode;
    public Vector2 WorldOrigin => _worldOrigin;
    public int Width => _width;
    public int Height => _height;
    public float CellSize => _cellSize;
    public bool AllowDiagonal => _allowDiagonal;
    public bool PreventDiagonalCornerCutting => _preventDiagonalCornerCutting;
    public int NearestWalkableSearchRadius => Mathf.Max(0, _nearestWalkableSearchRadius);
    public IReadOnlyList<NavigationTeleportLink> TeleportLinks => _teleportLinks;
    public string BakedSourceSummary => _bakedSourceSummary;

    /// <summary>
    /// 确保可走网格缓存已从遮罩 Sprite 构建。
    /// </summary>
    public bool TryPrepare(out string error)
    {
        if (_cacheBuilt && _walkableCache != null)
        {
            error = null;
            return true;
        }

        RebuildCache();
        error = _lastBuildError;
        return _cacheBuilt;
    }

    /// <summary>
    /// 将世界坐标转换为导航格坐标。
    /// </summary>
    public bool TryWorldToCell(Vector2 world, out Vector2Int cell)
    {
        var local = world - _worldOrigin;
        cell = new Vector2Int(
            Mathf.FloorToInt(local.x / _cellSize),
            Mathf.FloorToInt(local.y / _cellSize));
        return IsInside(cell);
    }

    /// <summary>
    /// 将导航格坐标转换为该格中心的世界坐标。
    /// </summary>
    public Vector2 CellToWorldCenter(Vector2Int cell)
    {
        return _worldOrigin + new Vector2(
            (cell.x + 0.5f) * _cellSize,
            (cell.y + 0.5f) * _cellSize);
    }

    /// <summary>
    /// 判断格子是否位于导航网格范围内。
    /// </summary>
    public bool IsInside(Vector2Int cell)
    {
        return cell.x >= 0 && cell.y >= 0 && cell.x < _width && cell.y < _height;
    }

    /// <summary>
    /// 判断格子是否可行走。
    /// </summary>
    public bool IsWalkable(Vector2Int cell)
    {
        if (!IsInside(cell)) return false;

        if (!_cacheBuilt || _walkableCache == null)
        {
            return false;
        }

        return _walkableCache[CellToIndex(cell)];
    }

    /// <summary>
    /// 返回格子的通行成本；越靠近障碍物通常越高。
    /// </summary>
    public float GetTraversalCost(Vector2Int cell)
    {
        if (!IsWalkable(cell)) return float.PositiveInfinity;

        if (_costCache == null)
            return 1f;

        return Mathf.Max(1f, _costCache[CellToIndex(cell)]);
    }

    /// <summary>
    /// 返回格子在线性数组中的索引。
    /// </summary>
    public int CellToIndex(Vector2Int cell)
    {
        return cell.y * _width + cell.x;
    }

    /// <summary>
    /// 返回线性索引对应的格子坐标。
    /// </summary>
    public Vector2Int IndexToCell(int index)
    {
        return new Vector2Int(index % _width, index / _width);
    }

    /// <summary>
    /// 从给定格附近寻找最近可走格，避免目标点落在障碍边缘时直接失败。
    /// </summary>
    public bool TryFindNearestWalkable(Vector2Int origin, int maxRadius, out Vector2Int nearest)
    {
        if (IsWalkable(origin))
        {
            nearest = origin;
            return true;
        }

        maxRadius = Mathf.Max(0, maxRadius);
        for (int radius = 1; radius <= maxRadius; radius++)
        {
            for (int y = -radius; y <= radius; y++)
            {
                for (int x = -radius; x <= radius; x++)
                {
                    if (Mathf.Abs(x) != radius && Mathf.Abs(y) != radius) continue;

                    var candidate = new Vector2Int(origin.x + x, origin.y + y);
                    if (IsWalkable(candidate))
                    {
                        nearest = candidate;
                        return true;
                    }
                }
            }
        }

        nearest = default;
        return false;
    }

    /// <summary>
    /// 收集从当前格可触发的传送出口。
    /// </summary>
    public void CollectTeleportExits(Vector2Int fromCell, List<NavigationTeleportExit> results)
    {
        results.Clear();
        if (_teleportLinks == null || _teleportLinks.Count == 0) return;

        foreach (var link in _teleportLinks)
        {
            if (link == null || !link.Enabled) continue;

            TryCollectTeleportExit(fromCell, link, link.EntranceWorld, link.ExitWorld,
                link.GetEntranceMatchRadius(_cellSize), link.Cost, false, results);

            if (link.Bidirectional)
            {
                TryCollectTeleportExit(fromCell, link, link.ExitWorld, link.EntranceWorld,
                    link.GetEntranceMatchRadius(_cellSize), link.Cost, true, results);
            }
        }
    }

    /// <summary>
    /// 构建导航网格调试纹理，用于场景覆盖显示或保存检查。
    /// </summary>
    public Texture2D BuildDebugTexture(Color walkableColor, Color blockedColor,
        Color teleportEntranceColor, Color teleportExitColor)
    {
        if (!TryPrepare(out _))
            return null;

        var texture = new Texture2D(_width, _height, TextureFormat.RGBA32, false)
        {
            filterMode = FilterMode.Point,
            wrapMode = TextureWrapMode.Clamp,
            name = $"{name}_debug_texture"
        };

        var pixels = new Color[_width * _height];
        for (int y = 0; y < _height; y++)
        {
            for (int x = 0; x < _width; x++)
            {
                var cell = new Vector2Int(x, y);
                pixels[CellToIndex(cell)] = GetDebugCellColor(cell, walkableColor, blockedColor);
            }
        }

        PaintTeleportDebugPixels(pixels, teleportEntranceColor, teleportExitColor);
        texture.SetPixels(pixels);
        texture.Apply();
        return texture;
    }

    /// <summary>
    /// 标记缓存失效，供编辑器或调试脚本修改参数后手动刷新。
    /// </summary>
    public void InvalidateCache()
    {
        _cacheBuilt = false;
        _walkableCache = null;
        _costCache = null;
        _lastBuildError = null;
    }

#if ODIN_INSPECTOR
    /// <summary>
    /// 清理运行时缓存；下一次寻路或调试图会重新构建缓存。
    /// </summary>
    [Button("清理运行时缓存", ButtonSizes.Medium)]
    [BoxGroup("NPC A* 导航网格/操作")]
    public void ClearRuntimeCacheForInspector()
    {
        InvalidateCache();
    }
#endif

    /// <summary>
    /// 写入编辑器烘焙出的静态导航格与通行成本。
    /// </summary>
    public void SetBakedGrid(Vector2 worldOrigin, int width, int height, float cellSize,
        IReadOnlyList<bool> walkable, IReadOnlyList<float> traversalCost, string sourceSummary)
    {
        _sourceMode = NavigationGridSourceMode.BakedCells;
        _worldOrigin = worldOrigin;
        _width = Mathf.Max(1, width);
        _height = Mathf.Max(1, height);
        _cellSize = Mathf.Max(0.01f, cellSize);

        int expected = _width * _height;
        _bakedWalkable = new List<bool>(expected);
        _bakedTraversalCost = new List<float>(expected);

        for (int i = 0; i < expected; i++)
        {
            bool isWalkable = walkable != null && i < walkable.Count && walkable[i];
            float cost = traversalCost != null && i < traversalCost.Count ? traversalCost[i] : 1f;
            _bakedWalkable.Add(isWalkable);
            _bakedTraversalCost.Add(Mathf.Max(1f, cost));
        }

        _bakedSourceSummary = sourceSummary;
        InvalidateCache();
    }

    /// <summary>
    /// 写入从场景传送点组件同步来的传送 link 副本。
    /// </summary>
    public void SetTeleportLinks(IReadOnlyList<NavigationTeleportLink> teleportLinks)
    {
        _teleportLinks = teleportLinks != null
            ? new List<NavigationTeleportLink>(teleportLinks)
            : new List<NavigationTeleportLink>();
        InvalidateCache();
    }

    /// <summary>
    /// 从遮罩 Sprite 重建可走格缓存。
    /// </summary>
    private void RebuildCache()
    {
        _cacheBuilt = false;
        _lastBuildError = null;

        if (_width <= 0 || _height <= 0 || _cellSize <= 0f)
        {
            _lastBuildError = "导航网格尺寸或格子大小非法。";
            return;
        }

        if (_sourceMode == NavigationGridSourceMode.BakedCells)
        {
            RebuildCacheFromBakedCells();
            return;
        }

        if (_walkableMaskSprite == null || _walkableMaskSprite.texture == null)
        {
            _lastBuildError = "未配置导航遮罩 Sprite。";
            return;
        }

        try
        {
            _walkableCache = new bool[_width * _height];
            _costCache = new float[_width * _height];
            var texture = _walkableMaskSprite.texture;
            var rect = _walkableMaskSprite.textureRect;

            for (int y = 0; y < _height; y++)
            {
                for (int x = 0; x < _width; x++)
                {
                    float u = (x + 0.5f) / _width;
                    float v = (y + 0.5f) / _height;
                    int px = Mathf.Clamp(Mathf.FloorToInt(rect.x + u * rect.width), 0, texture.width - 1);
                    int py = Mathf.Clamp(Mathf.FloorToInt(rect.y + v * rect.height), 0, texture.height - 1);
                    var color = texture.GetPixel(px, py);
                    int index = y * _width + x;
                    _walkableCache[index] = IsColorWalkable(color);
                    _costCache[index] = 1f;
                }
            }

            _cacheBuilt = true;
        }
        catch (UnityException ex)
        {
            _lastBuildError = $"导航遮罩 Sprite 无法读取像素，请开启 Read/Write: {ex.Message}";
            _walkableCache = null;
            _costCache = null;
        }
    }

    /// <summary>
    /// 从编辑器烘焙数据重建运行时缓存。
    /// </summary>
    private void RebuildCacheFromBakedCells()
    {
        int expected = _width * _height;
        if (_bakedWalkable == null || _bakedWalkable.Count != expected ||
            _bakedTraversalCost == null || _bakedTraversalCost.Count != expected)
        {
            _lastBuildError = "烘焙导航数据为空或尺寸不匹配，请重新 Bake。";
            return;
        }

        _walkableCache = new bool[expected];
        _costCache = new float[expected];

        for (int i = 0; i < expected; i++)
        {
            _walkableCache[i] = _bakedWalkable[i];
            _costCache[i] = Mathf.Max(1f, _bakedTraversalCost[i]);
        }

        _cacheBuilt = true;
    }

    /// <summary>
    /// 根据颜色阈值判断遮罩像素是否可走。
    /// </summary>
    private bool IsColorWalkable(Color color)
    {
        if (color.a <= _alphaThreshold)
            return _transparentPixelsAreWalkable;

        float luminance = color.r * 0.2126f + color.g * 0.7152f + color.b * 0.0722f;
        return _lightPixelsAreWalkable
            ? luminance >= _walkableThreshold
            : luminance <= _walkableThreshold;
    }

    /// <summary>
    /// 根据可走状态和成本生成调试颜色。
    /// </summary>
    private Color GetDebugCellColor(Vector2Int cell, Color walkableColor, Color blockedColor)
    {
        if (!IsWalkable(cell))
            return blockedColor;

        float cost = GetTraversalCost(cell);
        float t = Mathf.InverseLerp(1f, 5f, cost);
        var highCostColor = new Color(1f, 0.78f, 0.12f, walkableColor.a);
        return Color.Lerp(walkableColor, highCostColor, t);
    }

    /// <summary>
    /// 若当前格位于传送点触发半径内，则加入目标出口格。
    /// </summary>
    private void TryCollectTeleportExit(Vector2Int fromCell, NavigationTeleportLink link,
        Vector2 entranceWorld, Vector2 exitWorld, float entranceMatchRadius, float cost, bool isReverse,
        List<NavigationTeleportExit> results)
    {
        if (!TryWorldToCell(entranceWorld, out var entranceCell)) return;
        int radiusCells = Mathf.Max(0, Mathf.CeilToInt(entranceMatchRadius / _cellSize));
        int dx = Mathf.Abs(fromCell.x - entranceCell.x);
        int dy = Mathf.Abs(fromCell.y - entranceCell.y);
        if (dx > radiusCells || dy > radiusCells) return;

        if (!TryWorldToCell(exitWorld, out var exitCell)) return;
        if (!TryFindNearestWalkable(exitCell, _nearestWalkableSearchRadius, out var walkableExit)) return;

        var resolvedExitWorld = CellToWorldCenter(walkableExit);
        if (Vector2.Distance(resolvedExitWorld, exitWorld) > link.GetExitMatchRadius(_cellSize))
            return;

        results.Add(new NavigationTeleportExit(
            walkableExit,
            Mathf.Max(0.01f, cost),
            link.Id,
            entranceWorld,
            exitWorld,
            walkableExit,
            resolvedExitWorld,
            isReverse));
    }

    /// <summary>
    /// 在调试纹理上覆盖传送入口与出口颜色。
    /// </summary>
    private void PaintTeleportDebugPixels(Color[] pixels, Color entranceColor, Color exitColor)
    {
        if (_teleportLinks == null) return;

        foreach (var link in _teleportLinks)
        {
            if (link == null || !link.Enabled) continue;
            PaintWorldPoint(pixels, link.EntranceWorld, entranceColor);
            PaintWorldPoint(pixels, link.ExitWorld, exitColor);
        }
    }

    /// <summary>
    /// 在调试像素数组上绘制一个世界坐标对应的格子。
    /// </summary>
    private void PaintWorldPoint(Color[] pixels, Vector2 world, Color color)
    {
        if (!TryWorldToCell(world, out var cell) || !IsInside(cell)) return;
        pixels[CellToIndex(cell)] = color;
    }

    /// <summary>
    /// 编辑器参数变更时清理缓存，避免旧遮罩数据残留。
    /// </summary>
    private void OnValidate()
    {
        _width = Mathf.Max(1, _width);
        _height = Mathf.Max(1, _height);
        _cellSize = Mathf.Max(0.01f, _cellSize);
        _nearestWalkableSearchRadius = Mathf.Max(0, _nearestWalkableSearchRadius);
        InvalidateCache();
    }

    /// <summary>
    /// 判断当前是否使用旧遮罩 Sprite 兼容模式。
    /// </summary>
    private bool IsMaskSpriteMode()
    {
        return _sourceMode == NavigationGridSourceMode.MaskSprite;
    }

    /// <summary>
    /// 统计烘焙数据中的可走格数量。
    /// </summary>
    private int GetBakedWalkableCellCount()
    {
        if (_bakedWalkable == null) return 0;

        int count = 0;
        foreach (bool walkable in _bakedWalkable)
        {
            if (walkable)
                count++;
        }

        return count;
    }
}

/// <summary>
/// 导航网格的数据来源。
/// </summary>
public enum NavigationGridSourceMode
{
    MaskSprite,
    BakedCells,
}

/// <summary>
/// 单条传送连接配置。
/// </summary>
[Serializable]
public class NavigationTeleportLink
{
    [SerializeField] private string _id = "teleport";
    [SerializeField] private bool _enabled = true;
    [SerializeField] private Vector2 _entranceWorld;
    [SerializeField] private Vector2 _exitWorld;
    [SerializeField] private bool _bidirectional = true;
    [SerializeField] private float _triggerRadius = 0.25f;
#if ODIN_INSPECTOR
    [LabelText("入口匹配半径")]
#endif
    [Tooltip("0 表示使用默认值。用于传送点自主管理入口容差，不再由移动执行层硬编码。")]
    [SerializeField] private float _entranceMatchRadius = 0f;
#if ODIN_INSPECTOR
    [LabelText("出口匹配半径")]
#endif
    [Tooltip("0 表示使用默认值。用于传送点自主管理出口容差，不再由移动执行层硬编码。")]
    [SerializeField] private float _exitMatchRadius = 0f;
    [SerializeField] private float _cost = 1f;

    public NavigationTeleportLink()
    {
    }

    public string Id => _id;
    public bool Enabled => _enabled;
    public Vector2 EntranceWorld => _entranceWorld;
    public Vector2 ExitWorld => _exitWorld;
    public bool Bidirectional => _bidirectional;
    public float TriggerRadius => Mathf.Max(0f, _triggerRadius);
    public float Cost => Mathf.Max(0.01f, _cost);

    /// <summary>
    /// 从场景传送点组件创建运行时传送 link 数据副本。
    /// </summary>
    public static NavigationTeleportLink Create(string id, bool enabled, Vector2 entranceWorld,
        Vector2 exitWorld, bool bidirectional, float triggerRadius, float entranceMatchRadius,
        float exitMatchRadius, float cost)
    {
        return new NavigationTeleportLink
        {
            _id = string.IsNullOrWhiteSpace(id) ? "teleport" : id.Trim(),
            _enabled = enabled,
            _entranceWorld = entranceWorld,
            _exitWorld = exitWorld,
            _bidirectional = bidirectional,
            _triggerRadius = Mathf.Max(0f, triggerRadius),
            _entranceMatchRadius = Mathf.Max(0f, entranceMatchRadius),
            _exitMatchRadius = Mathf.Max(0f, exitMatchRadius),
            _cost = Mathf.Max(0.01f, cost),
        };
    }

    /// <summary>
    /// 返回入口匹配半径；未显式配置时使用触发半径与若干格尺寸的保守默认值。
    /// </summary>
    public float GetEntranceMatchRadius(float cellSize)
    {
        if (_entranceMatchRadius > 0f)
            return _entranceMatchRadius;

        return Mathf.Max(TriggerRadius, cellSize) + Mathf.Max(0.01f, cellSize) * 4f;
    }

    /// <summary>
    /// 返回出口匹配半径；未显式配置时使用两格半，兼容旧传送出口吸附逻辑。
    /// </summary>
    public float GetExitMatchRadius(float cellSize)
    {
        if (_exitMatchRadius > 0f)
            return _exitMatchRadius;

        return Mathf.Max(0.01f, cellSize) * 2.5f;
    }
}

/// <summary>
/// A* 搜索中可使用的传送出口。
/// </summary>
public readonly struct NavigationTeleportExit
{
    public readonly Vector2Int Cell;
    public readonly float Cost;
    public readonly string LinkId;
    public readonly Vector2 EntranceWorld;
    public readonly Vector2 ExitWorld;
    public readonly Vector2Int ResolvedExitCell;
    public readonly Vector2 ResolvedExitWorld;
    public readonly bool IsReverse;

    public NavigationTeleportExit(Vector2Int cell, float cost, string linkId, Vector2 entranceWorld,
        Vector2 exitWorld, Vector2Int resolvedExitCell, Vector2 resolvedExitWorld, bool isReverse)
    {
        Cell = cell;
        Cost = cost;
        LinkId = linkId;
        EntranceWorld = entranceWorld;
        ExitWorld = exitWorld;
        ResolvedExitCell = resolvedExitCell;
        ResolvedExitWorld = resolvedExitWorld;
        IsReverse = isReverse;
    }
}
