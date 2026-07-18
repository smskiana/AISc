using System;
using System.Collections.Generic;
using UnityEngine;

#if ODIN_INSPECTOR
using Sirenix.OdinInspector;
#endif

#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// 从地图 SpriteRenderer 与障碍物 SpriteRenderer 组合烘焙 NavigationGridAsset。
/// </summary>
[ExecuteAlways]
public class NavigationGridSpriteBaker : MonoBehaviour
{
#if ODIN_INSPECTOR
    [TitleGroup("NPC A* 导航烘焙")]
    [BoxGroup("NPC A* 导航烘焙/输出资产")]
    [Required("需要指定要写入的 NavigationGridAsset。")]
    [AssetSelector]
    [InlineEditor(InlineEditorModes.GUIOnly, Expanded = false)]
#endif
    [Header("Output")]
    [SerializeField] private NavigationGridAsset _targetGrid;

#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/地图 Sprite")]
    [InfoBox("地图 Sprite 定义可导航范围。可以指定 Root，也可以手动维护列表。")]
    [LabelText("地图 Root")]
#endif
    [Header("Map Sprites")]
    [SerializeField] private Transform _mapSpritesRoot;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/地图 Sprite")]
    [LabelText("地图列表")]
    [ListDrawerSettings(DefaultExpandedState = false, DraggableItems = true, ShowPaging = true)]
#endif
    [SerializeField] private List<SpriteRenderer> _mapSprites = new();

#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/障碍物 Sprite")]
    [InfoBox("障碍物 Sprite bounds 内不可走；距离障碍物越近，通行成本越高。")]
    [LabelText("障碍物 Root")]
#endif
    [Header("Obstacle Sprites")]
    [SerializeField] private Transform _obstacleSpritesRoot;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/障碍物 Sprite")]
    [LabelText("障碍物列表")]
    [ListDrawerSettings(DefaultExpandedState = false, DraggableItems = true, ShowPaging = true)]
#endif
    [SerializeField] private List<SpriteRenderer> _obstacleSprites = new();

#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/传送点")]
    [InfoBox("传送点组件决定入口、出口、半径、成本和双向规则；烘焙器只负责同步到导航资产。")]
    [LabelText("传送点 Root")]
#endif
    [Header("Teleport Points")]
    [SerializeField] private Transform _teleportPointsRoot;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/传送点")]
    [LabelText("传送点列表")]
    [ListDrawerSettings(DefaultExpandedState = false, DraggableItems = true, ShowPaging = true)]
#endif
    [SerializeField] private List<NavigationTeleportPoint> _teleportPoints = new();
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/传送点")]
    [LabelText("Bake 后同步传送点")]
#endif
    [SerializeField] private bool _syncTeleportLinksAfterBake = true;

#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/烘焙参数")]
    [LabelText("格子尺寸")]
    [MinValue(0.01f)]
#endif
    [Header("Bake Settings")]
    [SerializeField] private float _cellSize = 0.25f;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/烘焙参数")]
    [LabelText("范围外扩")]
#endif
    [SerializeField] private Vector2 _boundsPadding = new(0.5f, 0.5f);
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/烘焙参数")]
    [LabelText("包含未激活 Sprite")]
#endif
    [SerializeField] private bool _includeInactiveSprites;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/烘焙参数")]
    [LabelText("障碍膨胀")]
    [MinValue(0f)]
#endif
    [SerializeField] private float _obstacleInflation = 0.05f;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/烘焙参数")]
    [LabelText("障碍危险半径")]
    [MinValue(0.01f)]
#endif
    [SerializeField] private float _dangerRadius = 0.75f;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/烘焙参数")]
    [LabelText("贴近障碍最高成本")]
    [MinValue(1f)]
#endif
    [SerializeField] private float _maxNearObstacleCost = 5f;

#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/预览 Sprite")]
    [InfoBox("预览图会把低成本格显示为绿色，高成本格逐渐过渡到红色。")]
    [LabelText("预览 Renderer")]
#endif
    [Header("Preview")]
    [SerializeField] private SpriteRenderer _previewRenderer;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/预览 Sprite")]
    [LabelText("Bake 后自动刷新")]
#endif
    [SerializeField] private bool _refreshPreviewAfterBake = true;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/预览 Sprite")]
    [LabelText("预览排序")]
#endif
    [SerializeField] private int _previewSortingOrder = 120;
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/预览 Sprite")]
    [LabelText("低成本颜色")]
#endif
    [SerializeField] private Color _previewLowCostColor = new(0.1f, 0.95f, 0.25f, 0.35f);
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/预览 Sprite")]
    [LabelText("高成本颜色")]
#endif
    [SerializeField] private Color _previewHighCostColor = new(1f, 0.1f, 0.05f, 0.65f);
#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/预览 Sprite")]
    [LabelText("阻挡颜色")]
#endif
    [SerializeField] private Color _previewBlockedColor = new(0.55f, 0f, 0f, 0.55f);

    private Texture2D _previewTexture;
    private Sprite _previewSprite;

#if ODIN_INSPECTOR
    [BoxGroup("NPC A* 导航烘焙/状态")]
    [ShowInInspector]
    [ReadOnly]
    [LabelText("地图 Sprite 数")]
    private int MapSpriteCount => CollectSprites(_mapSpritesRoot, _mapSprites).Count;

    [BoxGroup("NPC A* 导航烘焙/状态")]
    [ShowInInspector]
    [ReadOnly]
    [LabelText("障碍物 Sprite 数")]
    private int ObstacleSpriteCount => CollectSprites(_obstacleSpritesRoot, _obstacleSprites).Count;

    [BoxGroup("NPC A* 导航烘焙/状态")]
    [ShowInInspector]
    [ReadOnly]
    [LabelText("传送点数")]
    private int TeleportPointCount => CollectTeleportPoints(_teleportPointsRoot, _teleportPoints).Count;

    [BoxGroup("NPC A* 导航烘焙/状态")]
    [ShowInInspector]
    [ReadOnly]
    [LabelText("预估网格")]
    private string EstimatedGridSize => BuildEstimatedGridSizeText();
#endif

    /// <summary>
    /// 从当前配置收集 SpriteRenderer 并写入目标导航资产。
    /// </summary>
#if ODIN_INSPECTOR
    [Button("Bake 到导航资产", ButtonSizes.Large)]
    [GUIColor(0.25f, 0.8f, 0.45f)]
    [BoxGroup("NPC A* 导航烘焙/操作")]
#endif
    [ContextMenu("Bake Navigation Grid From Sprites")]
    public void BakeToAsset()
    {
        if (_targetGrid == null)
        {
            Debug.LogWarning("[NavigationGridSpriteBaker] 未配置目标 NavigationGridAsset");
            return;
        }

        var mapSprites = CollectSprites(_mapSpritesRoot, _mapSprites);
        var obstacleSprites = CollectSprites(_obstacleSpritesRoot, _obstacleSprites);

        if (mapSprites.Count == 0)
        {
            Debug.LogWarning("[NavigationGridSpriteBaker] 没有可用地图 SpriteRenderer");
            return;
        }

        var mapBounds = CalculateCombinedBounds(mapSprites);
        var origin = new Vector2(
            mapBounds.min.x - _boundsPadding.x,
            mapBounds.min.y - _boundsPadding.y);
        var size = new Vector2(
            mapBounds.size.x + _boundsPadding.x * 2f,
            mapBounds.size.y + _boundsPadding.y * 2f);

        int width = Mathf.Max(1, Mathf.CeilToInt(size.x / Mathf.Max(0.01f, _cellSize)));
        int height = Mathf.Max(1, Mathf.CeilToInt(size.y / Mathf.Max(0.01f, _cellSize)));
        int count = width * height;
        var walkable = new List<bool>(count);
        var costs = new List<float>(count);

        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                var cellCenter = origin + new Vector2((x + 0.5f) * _cellSize, (y + 0.5f) * _cellSize);
                bool insideMap = IsPointInsideAnyBounds(cellCenter, mapSprites);
                float nearestObstacleDistance = FindNearestObstacleDistance(cellCenter, obstacleSprites);
                bool blocked = insideMap && nearestObstacleDistance <= Mathf.Max(0f, _obstacleInflation);

                walkable.Add(insideMap && !blocked);
                costs.Add(insideMap && !blocked
                    ? CalculateTraversalCost(nearestObstacleDistance)
                    : 1f);
            }
        }

        string summary = BuildSourceSummary(mapSprites.Count, obstacleSprites.Count, width, height);
        _targetGrid.SetBakedGrid(origin, width, height, _cellSize, walkable, costs, summary);
        if (_syncTeleportLinksAfterBake && HasTeleportPointSource())
            SyncTeleportLinksToAsset();

#if UNITY_EDITOR
        EditorUtility.SetDirty(_targetGrid);
        AssetDatabase.SaveAssets();
#endif

        if (_refreshPreviewAfterBake)
            RebuildPreviewSprite();

        Debug.Log($"[NavigationGridSpriteBaker] Bake 完成: {summary}");
    }

    /// <summary>
    /// 从地图 Root 重新收集地图 SpriteRenderer。
    /// </summary>
#if ODIN_INSPECTOR
    [Button("从地图 Root 收集", ButtonSizes.Medium)]
    [BoxGroup("NPC A* 导航烘焙/操作")]
#endif
    [ContextMenu("Collect Map Sprites From Root")]
    public void CollectMapSpritesFromRoot()
    {
        _mapSprites = CollectSprites(_mapSpritesRoot, null);
        Debug.Log($"[NavigationGridSpriteBaker] 已收集地图 Sprite: {_mapSprites.Count}");
    }

    /// <summary>
    /// 从障碍物 Root 重新收集障碍物 SpriteRenderer。
    /// </summary>
#if ODIN_INSPECTOR
    [Button("从障碍物 Root 收集", ButtonSizes.Medium)]
    [BoxGroup("NPC A* 导航烘焙/操作")]
#endif
    [ContextMenu("Collect Obstacle Sprites From Root")]
    public void CollectObstacleSpritesFromRoot()
    {
        _obstacleSprites = CollectSprites(_obstacleSpritesRoot, null);
        Debug.Log($"[NavigationGridSpriteBaker] 已收集障碍物 Sprite: {_obstacleSprites.Count}");
    }

    /// <summary>
    /// 从传送点 Root 重新收集传送点组件。
    /// </summary>
#if ODIN_INSPECTOR
    [Button("从传送点 Root 收集", ButtonSizes.Medium)]
    [BoxGroup("NPC A* 导航烘焙/操作")]
#endif
    [ContextMenu("Collect Teleport Points From Root")]
    public void CollectTeleportPointsFromRoot()
    {
        _teleportPoints = CollectTeleportPoints(_teleportPointsRoot, null);
        Debug.Log($"[NavigationGridSpriteBaker] 已收集传送点组件: {_teleportPoints.Count}");
    }

    /// <summary>
    /// 将场景传送点组件同步为目标导航资产中的运行时传送 links。
    /// </summary>
#if ODIN_INSPECTOR
    [Button("同步传送点到导航资产", ButtonSizes.Medium)]
    [GUIColor(0.35f, 0.75f, 1f)]
    [BoxGroup("NPC A* 导航烘焙/操作")]
#endif
    [ContextMenu("Sync Teleport Points To Navigation Asset")]
    public void SyncTeleportLinksToAsset()
    {
        if (_targetGrid == null)
        {
            Debug.LogWarning("[NavigationGridSpriteBaker] 未配置目标 NavigationGridAsset，无法同步传送点");
            return;
        }

        var points = CollectTeleportPoints(_teleportPointsRoot, _teleportPoints);
        if (points.Count == 0)
        {
            Debug.LogWarning("[NavigationGridSpriteBaker] 没有可同步的 NavigationTeleportPoint");
            return;
        }

        var links = BuildTeleportLinks(points);
        _targetGrid.SetTeleportLinks(links);

#if UNITY_EDITOR
        EditorUtility.SetDirty(_targetGrid);
        AssetDatabase.SaveAssets();
#endif

        Debug.Log($"[NavigationGridSpriteBaker] 已同步传送 links: {links.Count}");
    }

    /// <summary>
    /// 清空地图和障碍物显式列表。
    /// </summary>
#if ODIN_INSPECTOR
    [Button("清空显式列表", ButtonSizes.Small)]
    [GUIColor(1f, 0.72f, 0.25f)]
    [BoxGroup("NPC A* 导航烘焙/操作")]
#endif
    [ContextMenu("Clear Explicit Sprite Lists")]
    public void ClearExplicitSpriteLists()
    {
        _mapSprites.Clear();
        _obstacleSprites.Clear();
        _teleportPoints.Clear();
    }

    /// <summary>
    /// 基于目标导航资产刷新绿到红的成本场预览 Sprite。
    /// </summary>
#if ODIN_INSPECTOR
    [Button("刷新绿→红预览 Sprite", ButtonSizes.Large)]
    [GUIColor(0.35f, 0.9f, 0.35f)]
    [BoxGroup("NPC A* 导航烘焙/预览 Sprite")]
#endif
    [ContextMenu("Rebuild Green Red Preview Sprite")]
    public void RebuildPreviewSprite()
    {
        if (_targetGrid == null)
        {
            Debug.LogWarning("[NavigationGridSpriteBaker] 未配置目标 NavigationGridAsset，无法生成预览");
            return;
        }

        if (_previewRenderer == null)
        {
            Debug.LogWarning("[NavigationGridSpriteBaker] 未配置预览 SpriteRenderer");
            return;
        }

        if (!_targetGrid.TryPrepare(out var error))
        {
            Debug.LogWarning($"[NavigationGridSpriteBaker] 导航网格未准备好，无法生成预览: {error}");
            return;
        }

        DestroyGeneratedPreviewObjects();

        _previewTexture = BuildGreenRedPreviewTexture();
        float pixelsPerUnit = 1f / Mathf.Max(0.01f, _targetGrid.CellSize);
        _previewSprite = Sprite.Create(
            _previewTexture,
            new Rect(0, 0, _previewTexture.width, _previewTexture.height),
            Vector2.zero,
            pixelsPerUnit);

        _previewRenderer.sprite = _previewSprite;
        _previewRenderer.sortingOrder = _previewSortingOrder;
        _previewRenderer.transform.position = new Vector3(
            _targetGrid.WorldOrigin.x,
            _targetGrid.WorldOrigin.y,
            _previewRenderer.transform.position.z);
    }

    /// <summary>
    /// 清理当前烘焙器生成的预览 Sprite。
    /// </summary>
#if ODIN_INSPECTOR
    [Button("清空预览 Sprite", ButtonSizes.Small)]
    [GUIColor(1f, 0.72f, 0.25f)]
    [BoxGroup("NPC A* 导航烘焙/预览 Sprite")]
#endif
    [ContextMenu("Clear Preview Sprite")]
    public void ClearPreviewSprite()
    {
        if (_previewRenderer != null && _previewRenderer.sprite == _previewSprite)
            _previewRenderer.sprite = null;

        DestroyGeneratedPreviewObjects();
    }

    /// <summary>
    /// 从显式列表和根节点子级收集可用 SpriteRenderer。
    /// </summary>
    private List<SpriteRenderer> CollectSprites(Transform root, List<SpriteRenderer> explicitSprites)
    {
        var results = new List<SpriteRenderer>();
        var seen = new HashSet<SpriteRenderer>();

        if (explicitSprites != null)
        {
            foreach (var sprite in explicitSprites)
                TryAddSprite(sprite, results, seen);
        }

        if (root != null)
        {
            var children = root.GetComponentsInChildren<SpriteRenderer>(_includeInactiveSprites);
            foreach (var sprite in children)
                TryAddSprite(sprite, results, seen);
        }

        return results;
    }

    /// <summary>
    /// 从显式列表和根节点子级收集可用 NavigationTeleportPoint。
    /// </summary>
    private List<NavigationTeleportPoint> CollectTeleportPoints(Transform root,
        List<NavigationTeleportPoint> explicitPoints)
    {
        var results = new List<NavigationTeleportPoint>();
        var seen = new HashSet<NavigationTeleportPoint>();

        if (explicitPoints != null)
        {
            foreach (var point in explicitPoints)
                TryAddTeleportPoint(point, results, seen);
        }

        if (root != null)
        {
            var children = root.GetComponentsInChildren<NavigationTeleportPoint>(_includeInactiveSprites);
            foreach (var point in children)
                TryAddTeleportPoint(point, results, seen);
        }

        return results;
    }

    /// <summary>
    /// 向传送点列表添加一个未重复的可用组件。
    /// </summary>
    private void TryAddTeleportPoint(NavigationTeleportPoint point,
        List<NavigationTeleportPoint> results, HashSet<NavigationTeleportPoint> seen)
    {
        if (point == null) return;
        if (!_includeInactiveSprites && !point.gameObject.activeInHierarchy) return;
        if (!seen.Add(point)) return;
        results.Add(point);
    }

    /// <summary>
    /// 将场景传送点组件转换为导航资产使用的 link 列表。
    /// </summary>
    private List<NavigationTeleportLink> BuildTeleportLinks(List<NavigationTeleportPoint> points)
    {
        var links = new List<NavigationTeleportLink>();
        var seenIds = new HashSet<string>();
        var seenBidirectionalPairs = new HashSet<string>();

        foreach (var point in points)
        {
            if (point == null) continue;
            if (!point.ExportsLink) continue;

            if (point.Bidirectional && point.PairedPoint != null)
            {
                string pairKey = BuildTeleportPairKey(point, point.PairedPoint);
                if (!seenBidirectionalPairs.Add(pairKey))
                {
                    Debug.LogWarning($"[NavigationGridSpriteBaker] 跳过重复双向传送点 pair: {point.name}");
                    continue;
                }
            }

            if (!point.TryBuildLink(out var link, out var failureReason))
            {
                Debug.LogWarning($"[NavigationGridSpriteBaker] 跳过传送点 {point.name}: {failureReason}");
                continue;
            }

            if (!seenIds.Add(link.Id))
            {
                Debug.LogWarning($"[NavigationGridSpriteBaker] 跳过重复传送 link id={link.Id}");
                continue;
            }

            links.Add(link);
        }

        return links;
    }

    /// <summary>
    /// 生成双向传送点配对键，避免同一对点被两个组件重复写入。
    /// </summary>
    private string BuildTeleportPairKey(NavigationTeleportPoint a, NavigationTeleportPoint b)
    {
        int idA = a.GetInstanceID();
        int idB = b.GetInstanceID();
        return idA < idB ? $"{idA}:{idB}" : $"{idB}:{idA}";
    }

    /// <summary>
    /// 判断烘焙器是否配置了传送点来源。
    /// </summary>
    private bool HasTeleportPointSource()
    {
        return _teleportPointsRoot != null || (_teleportPoints != null && _teleportPoints.Count > 0);
    }

    /// <summary>
    /// 向结果列表添加一个可用且未重复的 SpriteRenderer。
    /// </summary>
    private void TryAddSprite(SpriteRenderer sprite, List<SpriteRenderer> results, HashSet<SpriteRenderer> seen)
    {
        if (sprite == null || sprite.sprite == null) return;
        if (!_includeInactiveSprites && !sprite.gameObject.activeInHierarchy) return;
        if (!seen.Add(sprite)) return;
        results.Add(sprite);
    }

    /// <summary>
    /// 计算多个 SpriteRenderer 的世界 bounds 并集。
    /// </summary>
    private Bounds CalculateCombinedBounds(List<SpriteRenderer> sprites)
    {
        var bounds = sprites[0].bounds;
        for (int i = 1; i < sprites.Count; i++)
            bounds.Encapsulate(sprites[i].bounds);
        return bounds;
    }

    /// <summary>
    /// 判断点是否落在任一地图 SpriteRenderer 的 bounds 内。
    /// </summary>
    private bool IsPointInsideAnyBounds(Vector2 point, List<SpriteRenderer> sprites)
    {
        foreach (var sprite in sprites)
        {
            if (ContainsPoint2D(sprite.bounds, point))
                return true;
        }

        return false;
    }

    /// <summary>
    /// 找到点到最近障碍物 bounds 的二维距离。
    /// </summary>
    private float FindNearestObstacleDistance(Vector2 point, List<SpriteRenderer> obstacleSprites)
    {
        if (obstacleSprites.Count == 0)
            return float.PositiveInfinity;

        float nearest = float.PositiveInfinity;
        foreach (var obstacle in obstacleSprites)
        {
            float distance = DistanceToBounds2D(point, obstacle.bounds);
            if (distance < nearest)
                nearest = distance;
        }

        return nearest;
    }

    /// <summary>
    /// 根据离障碍物距离计算通行成本。
    /// </summary>
    private float CalculateTraversalCost(float nearestObstacleDistance)
    {
        if (float.IsPositiveInfinity(nearestObstacleDistance))
            return 1f;

        float dangerRadius = Mathf.Max(0.01f, _dangerRadius);
        if (nearestObstacleDistance >= dangerRadius)
            return 1f;

        float t = 1f - Mathf.Clamp01(nearestObstacleDistance / dangerRadius);
        float smoothed = t * t;
        return Mathf.Lerp(1f, Mathf.Max(1f, _maxNearObstacleCost), smoothed);
    }

    /// <summary>
    /// 生成从绿色到红色的通行成本预览纹理。
    /// </summary>
    private Texture2D BuildGreenRedPreviewTexture()
    {
        var texture = new Texture2D(_targetGrid.Width, _targetGrid.Height, TextureFormat.RGBA32, false)
        {
            filterMode = FilterMode.Point,
            wrapMode = TextureWrapMode.Clamp,
            name = $"{_targetGrid.name}_green_red_preview"
        };

        var pixels = new Color[_targetGrid.Width * _targetGrid.Height];
        float maxCost = Mathf.Max(1f, _maxNearObstacleCost);
        for (int y = 0; y < _targetGrid.Height; y++)
        {
            for (int x = 0; x < _targetGrid.Width; x++)
            {
                var cell = new Vector2Int(x, y);
                int index = _targetGrid.CellToIndex(cell);
                if (!_targetGrid.IsWalkable(cell))
                {
                    pixels[index] = _previewBlockedColor;
                    continue;
                }

                float cost = _targetGrid.GetTraversalCost(cell);
                float t = Mathf.InverseLerp(1f, maxCost, cost);
                pixels[index] = Color.Lerp(_previewLowCostColor, _previewHighCostColor, t);
            }
        }

        texture.SetPixels(pixels);
        texture.Apply();
        return texture;
    }

    /// <summary>
    /// 销毁当前烘焙器生成的临时预览纹理和 Sprite。
    /// </summary>
    private void DestroyGeneratedPreviewObjects()
    {
        DestroyGeneratedObject(_previewSprite);
        DestroyGeneratedObject(_previewTexture);
        _previewSprite = null;
        _previewTexture = null;
    }

    /// <summary>
    /// 根据当前运行状态销毁临时 Unity 对象。
    /// </summary>
    private void DestroyGeneratedObject(UnityEngine.Object obj)
    {
        if (obj == null) return;

        if (Application.isPlaying)
            Destroy(obj);
        else
            DestroyImmediate(obj);
    }

    /// <summary>
    /// 判断二维点是否位于 Bounds 的 XY 投影内。
    /// </summary>
    private bool ContainsPoint2D(Bounds bounds, Vector2 point)
    {
        return point.x >= bounds.min.x && point.x <= bounds.max.x &&
               point.y >= bounds.min.y && point.y <= bounds.max.y;
    }

    /// <summary>
    /// 计算二维点到 Bounds XY 投影的最短距离，点在内部时返回 0。
    /// </summary>
    private float DistanceToBounds2D(Vector2 point, Bounds bounds)
    {
        float dx = Mathf.Max(bounds.min.x - point.x, 0f, point.x - bounds.max.x);
        float dy = Mathf.Max(bounds.min.y - point.y, 0f, point.y - bounds.max.y);
        return Mathf.Sqrt(dx * dx + dy * dy);
    }

    /// <summary>
    /// 生成写入资产的烘焙来源摘要。
    /// </summary>
    private string BuildSourceSummary(int mapCount, int obstacleCount, int width, int height)
    {
        return $"sprites={mapCount}, obstacles={obstacleCount}, size={width}x{height}, cell={_cellSize:0.###}";
    }

    /// <summary>
    /// 构建当前配置下的预估网格尺寸文案。
    /// </summary>
    private string BuildEstimatedGridSizeText()
    {
        var mapSprites = CollectSprites(_mapSpritesRoot, _mapSprites);
        if (mapSprites.Count == 0)
            return "无地图 Sprite";

        var bounds = CalculateCombinedBounds(mapSprites);
        float safeCellSize = Mathf.Max(0.01f, _cellSize);
        int width = Mathf.Max(1, Mathf.CeilToInt((bounds.size.x + _boundsPadding.x * 2f) / safeCellSize));
        int height = Mathf.Max(1, Mathf.CeilToInt((bounds.size.y + _boundsPadding.y * 2f) / safeCellSize));
        return $"{width} x {height} ({width * height} cells)";
    }

    /// <summary>
    /// 编辑器中保证烘焙参数保持在可用范围内。
    /// </summary>
    private void OnValidate()
    {
        _cellSize = Mathf.Max(0.01f, _cellSize);
        _boundsPadding.x = Mathf.Max(0f, _boundsPadding.x);
        _boundsPadding.y = Mathf.Max(0f, _boundsPadding.y);
        _obstacleInflation = Mathf.Max(0f, _obstacleInflation);
        _dangerRadius = Mathf.Max(0.01f, _dangerRadius);
        _maxNearObstacleCost = Mathf.Max(1f, _maxNearObstacleCost);
    }
}
