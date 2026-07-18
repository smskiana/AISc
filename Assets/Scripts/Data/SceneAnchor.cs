using System;
using System.Collections.Generic;
using UnityEngine;

#if ODIN_INSPECTOR
using Sirenix.OdinInspector;
#endif

/// <summary>
/// 场景位置锚点：把 location_id 绑定到场景中的一个或多个可站区域。
/// 后端只传 location_id，Unity 通过本组件决定角色实际落点。
/// </summary>
public class SceneAnchor : MonoBehaviour
{
#if ODIN_INSPECTOR
    [TitleGroup("Scene Anchor 场景语义锚点")]
    [BoxGroup("Scene Anchor 场景语义锚点/绑定")]
    [LabelText("Location ID")]
#endif
    [Header("绑定")]
    public string LocationId;

#if ODIN_INSPECTOR
    [BoxGroup("Scene Anchor 场景语义锚点/兼容偏移")]
    [LabelText("旧随机偏移半径")]
    [MinValue(0f)]
#endif
    [Header("移动")]
    public float RandomOffsetRadius = 1.5f;

#if ODIN_INSPECTOR
    [BoxGroup("Scene Anchor 场景语义锚点/区域组合")]
    [ListDrawerSettings(DefaultExpandedState = true, DraggableItems = true)]
    [LabelText("可站区域")]
#endif
    [Header("区域组合")]
    [SerializeField] private List<SceneAnchorArea> _areas = new();

    public IReadOnlyList<SceneAnchorArea> Areas => _areas;

    /// <summary>
    /// 是否配置了新的区域组合。
    /// </summary>
    public bool HasCustomAreas
    {
        get
        {
            foreach (var area in _areas)
            {
                if (area != null && area.Enabled)
                    return true;
            }

            return false;
        }
    }

    /// <summary>
    /// 从 Anchor 区域中采样一个世界坐标；未配置区域时使用旧圆形半径。
    /// </summary>
    public Vector2 SamplePoint(float fallbackRadius = 1.5f)
    {
        var area = PickArea();
        if (area != null)
            return area.SampleWorldPoint(transform);

        var pos = transform.position;
        float radius = RandomOffsetRadius > 0f ? RandomOffsetRadius : fallbackRadius;
        var offset = radius > 0f ? UnityEngine.Random.insideUnitCircle * radius : Vector2.zero;
        return new Vector2(pos.x, pos.y) + offset;
    }

    /// <summary>
    /// 从 Anchor 区域中生成多个候选世界坐标，供寻路系统挑选可达点。
    /// </summary>
    public List<Vector2> SampleCandidatePoints(int count, float fallbackRadius = 1.5f)
    {
        count = Mathf.Max(1, count);
        var results = new List<Vector2>(count + _areas.Count + 1);
        var fallbackPoints = new List<Vector2>(_areas.Count + 1);

        if (HasCustomAreas)
        {
            foreach (var area in _areas)
            {
                if (area == null || !area.Enabled) continue;
                fallbackPoints.Add(area.GetWorldCenter(transform));
            }
        }
        else
        {
            var pos = transform.position;
            fallbackPoints.Add(new Vector2(pos.x, pos.y));
        }

        while (results.Count < count)
            results.Add(SamplePoint(fallbackRadius));

        // 随机点优先，固定中心点只作为寻路失败后的兜底候选。
        results.AddRange(fallbackPoints);
        return results;
    }

    /// <summary>
    /// 计算世界坐标到 Anchor 区域的近似距离，用于反查最近 location。
    /// </summary>
    public float DistanceTo(Vector2 worldPoint)
    {
        if (!HasCustomAreas)
            return Vector2.Distance(worldPoint, new Vector2(transform.position.x, transform.position.y));

        float best = float.MaxValue;
        foreach (var area in _areas)
        {
            if (area == null || !area.Enabled) continue;
            best = Mathf.Min(best, area.DistanceToWorldPoint(transform, worldPoint));
        }

        return best;
    }

    /// <summary>
    /// 从已启用区域中按权重选一个区域。
    /// </summary>
    private SceneAnchorArea PickArea()
    {
        int totalWeight = 0;
        foreach (var area in _areas)
        {
            if (area == null || !area.Enabled) continue;
            totalWeight += Mathf.Max(1, area.Weight);
        }

        if (totalWeight <= 0)
            return null;

        int roll = UnityEngine.Random.Range(0, totalWeight);
        foreach (var area in _areas)
        {
            if (area == null || !area.Enabled) continue;

            roll -= Mathf.Max(1, area.Weight);
            if (roll < 0)
                return area;
        }

        return null;
    }

    void OnEnable()
    {
        SceneAnchorRegistry.MarkDirty();
    }

    void OnDisable()
    {
        SceneAnchorRegistry.MarkDirty();
    }

    void OnValidate()
    {
        SceneAnchorRegistry.MarkDirty();
    }

    void OnDrawGizmos()
    {
        Gizmos.color = new Color(1f, 0.9f, 0.2f, 0.9f);
        Gizmos.DrawSphere(transform.position, 0.08f);

        if (HasCustomAreas)
        {
            foreach (var area in _areas)
            {
                if (area == null || !area.Enabled) continue;
                area.DrawGizmos(transform);
            }

            return;
        }

        if (RandomOffsetRadius > 0f)
        {
            Gizmos.color = new Color(1f, 0.9f, 0.2f, 0.25f);
            Gizmos.DrawWireSphere(transform.position, RandomOffsetRadius);
        }
    }
}

/// <summary>
/// SceneAnchor 的单个可站区域，支持圆形和矩形。
/// </summary>
[Serializable]
public class SceneAnchorArea
{
#if ODIN_INSPECTOR
    [LabelText("名称")]
#endif
    public string Name = "area";
#if ODIN_INSPECTOR
    [LabelText("启用")]
#endif
    public bool Enabled = true;
#if ODIN_INSPECTOR
    [EnumToggleButtons]
    [LabelText("形状")]
#endif
    public SceneAnchorAreaShape Shape = SceneAnchorAreaShape.Circle;
#if ODIN_INSPECTOR
    [LabelText("本地偏移")]
#endif
    public Vector2 LocalOffset = Vector2.zero;
#if ODIN_INSPECTOR
    [ShowIf(nameof(IsCircle))]
    [LabelText("圆形半径")]
    [MinValue(0f)]
#endif
    public float Radius = 1f;
#if ODIN_INSPECTOR
    [ShowIf(nameof(IsRectangle))]
    [LabelText("方形尺寸")]
    [MinValue(0.01f)]
#endif
    public Vector2 Size = Vector2.one;
#if ODIN_INSPECTOR
    [LabelText("采样权重")]
    [MinValue(1)]
#endif
    public int Weight = 1;

    /// <summary>
    /// 在该区域内采样一个世界坐标。
    /// </summary>
    public Vector2 SampleWorldPoint(Transform anchorTransform)
    {
        Vector2 local = LocalOffset;
        if (Shape == SceneAnchorAreaShape.Rectangle)
        {
            var half = GetHalfSize();
            local += new Vector2(
                UnityEngine.Random.Range(-half.x, half.x),
                UnityEngine.Random.Range(-half.y, half.y));
        }
        else
        {
            local += UnityEngine.Random.insideUnitCircle * Mathf.Max(0f, Radius);
        }

        var world = anchorTransform.TransformPoint(new Vector3(local.x, local.y, 0f));
        return new Vector2(world.x, world.y);
    }

    /// <summary>
    /// 返回该区域中心的世界坐标。
    /// </summary>
    public Vector2 GetWorldCenter(Transform anchorTransform)
    {
        var world = anchorTransform.TransformPoint(new Vector3(LocalOffset.x, LocalOffset.y, 0f));
        return new Vector2(world.x, world.y);
    }

    /// <summary>
    /// 计算世界坐标到该区域边界的近似距离，区域内部返回 0。
    /// </summary>
    public float DistanceToWorldPoint(Transform anchorTransform, Vector2 worldPoint)
    {
        var local3 = anchorTransform.InverseTransformPoint(new Vector3(worldPoint.x, worldPoint.y, anchorTransform.position.z));
        var local = new Vector2(local3.x, local3.y) - LocalOffset;

        if (Shape == SceneAnchorAreaShape.Rectangle)
        {
            var half = GetHalfSize();
            float dx = Mathf.Max(Mathf.Abs(local.x) - half.x, 0f);
            float dy = Mathf.Max(Mathf.Abs(local.y) - half.y, 0f);
            return Mathf.Sqrt(dx * dx + dy * dy);
        }

        return Mathf.Max(0f, local.magnitude - Mathf.Max(0f, Radius));
    }

    /// <summary>
    /// 绘制该区域的编辑器调试 Gizmo。
    /// </summary>
    public void DrawGizmos(Transform anchorTransform)
    {
        var oldMatrix = Gizmos.matrix;
        Gizmos.matrix = anchorTransform.localToWorldMatrix;
        Gizmos.color = Shape == SceneAnchorAreaShape.Rectangle
            ? new Color(0.2f, 0.85f, 1f, 0.35f)
            : new Color(1f, 0.9f, 0.2f, 0.35f);

        if (Shape == SceneAnchorAreaShape.Rectangle)
        {
            Gizmos.DrawWireCube(new Vector3(LocalOffset.x, LocalOffset.y, 0f),
                new Vector3(Mathf.Max(0.01f, Size.x), Mathf.Max(0.01f, Size.y), 0.01f));
        }
        else
        {
            Gizmos.DrawWireSphere(new Vector3(LocalOffset.x, LocalOffset.y, 0f), Mathf.Max(0f, Radius));
        }

        Gizmos.matrix = oldMatrix;
    }

    /// <summary>
    /// 返回矩形区域半尺寸。
    /// </summary>
    private Vector2 GetHalfSize()
    {
        return new Vector2(Mathf.Max(0.01f, Size.x) * 0.5f, Mathf.Max(0.01f, Size.y) * 0.5f);
    }

#if ODIN_INSPECTOR
    /// <summary>
    /// Odin Inspector 条件显示：当前区域是否为圆形。
    /// </summary>
    private bool IsCircle()
    {
        return Shape == SceneAnchorAreaShape.Circle;
    }

    /// <summary>
    /// Odin Inspector 条件显示：当前区域是否为矩形。
    /// </summary>
    private bool IsRectangle()
    {
        return Shape == SceneAnchorAreaShape.Rectangle;
    }
#endif
}

/// <summary>
/// SceneAnchor 可站区域形状。
/// </summary>
public enum SceneAnchorAreaShape
{
    Circle,
    Rectangle,
}
