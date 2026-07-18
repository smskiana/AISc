using UnityEngine;

#if ODIN_INSPECTOR
using Sirenix.OdinInspector;
#endif

/// <summary>
/// 场景侧导航传送点组件，拥有传送半径、成本、配对目标和双向规则。
/// </summary>
[ExecuteAlways]
public class NavigationTeleportPoint : MonoBehaviour
{
#if ODIN_INSPECTOR
    [TitleGroup("导航传送点")]
    [BoxGroup("导航传送点/身份")]
    [LabelText("Link ID")]
#endif
    [Header("Identity")]
    [SerializeField] private string _id;

#if ODIN_INSPECTOR
    [BoxGroup("导航传送点/身份")]
    [LabelText("启用")]
#endif
    [SerializeField] private bool _enabled = true;

#if ODIN_INSPECTOR
    [BoxGroup("导航传送点/身份")]
    [LabelText("导出 Link")]
#endif
    [Tooltip("关闭后仍可作为配对目标，但不会向导航资产写入 link。")]
    [SerializeField] private bool _exportsLink = true;

#if ODIN_INSPECTOR
    [BoxGroup("导航传送点/配对")]
    [Required("需要指定传送出口点。")]
    [LabelText("出口传送点")]
#endif
    [Header("Pair")]
    [SerializeField] private NavigationTeleportPoint _pairedPoint;

#if ODIN_INSPECTOR
    [BoxGroup("导航传送点/配对")]
    [LabelText("双向")]
#endif
    [SerializeField] private bool _bidirectional = true;

#if ODIN_INSPECTOR
    [BoxGroup("导航传送点/规则")]
    [MinValue(0f)]
    [LabelText("触发半径")]
#endif
    [Header("Rules")]
    [SerializeField] private float _triggerRadius = 0.35f;

#if ODIN_INSPECTOR
    [BoxGroup("导航传送点/规则")]
    [MinValue(0f)]
    [LabelText("入口匹配半径")]
#endif
    [Tooltip("0 表示使用 NavigationTeleportLink 默认值。")]
    [SerializeField] private float _entranceMatchRadius;

#if ODIN_INSPECTOR
    [BoxGroup("导航传送点/规则")]
    [MinValue(0f)]
    [LabelText("出口匹配半径")]
#endif
    [Tooltip("0 表示使用 NavigationTeleportLink 默认值。")]
    [SerializeField] private float _exitMatchRadius;

#if ODIN_INSPECTOR
    [BoxGroup("导航传送点/规则")]
    [MinValue(0.01f)]
    [LabelText("通行成本")]
#endif
    [SerializeField] private float _cost = 1f;

    public string Id => string.IsNullOrWhiteSpace(_id) ? gameObject.name : _id.Trim();
    public bool Enabled => _enabled;
    public bool ExportsLink => _exportsLink;
    public NavigationTeleportPoint PairedPoint => _pairedPoint;
    public bool Bidirectional => _bidirectional;
    public float TriggerRadius => Mathf.Max(0f, _triggerRadius);
    public float EntranceMatchRadius => Mathf.Max(0f, _entranceMatchRadius);
    public float ExitMatchRadius => Mathf.Max(0f, _exitMatchRadius);
    public float Cost => Mathf.Max(0.01f, _cost);
    public Vector2 WorldPosition => transform.position;

    /// <summary>
    /// 从当前场景组件构建导航资产使用的运行时传送 link。
    /// </summary>
    public bool TryBuildLink(out NavigationTeleportLink link, out string failureReason)
    {
        link = null;
        failureReason = null;

        if (!_enabled)
        {
            failureReason = $"{name} 已禁用。";
            return false;
        }

        if (!_exportsLink)
        {
            failureReason = $"{name} 仅作为配对目标，不导出 link。";
            return false;
        }

        if (_pairedPoint == null)
        {
            failureReason = $"{name} 未配置出口传送点。";
            return false;
        }

        link = NavigationTeleportLink.Create(
            Id,
            true,
            WorldPosition,
            _pairedPoint.WorldPosition,
            _bidirectional,
            TriggerRadius,
            EntranceMatchRadius,
            ExitMatchRadius,
            Cost);
        return true;
    }

    /// <summary>
    /// 编辑器中保证半径和成本处于合法范围。
    /// </summary>
    private void OnValidate()
    {
        _triggerRadius = Mathf.Max(0f, _triggerRadius);
        _entranceMatchRadius = Mathf.Max(0f, _entranceMatchRadius);
        _exitMatchRadius = Mathf.Max(0f, _exitMatchRadius);
        _cost = Mathf.Max(0.01f, _cost);
    }

    /// <summary>
    /// 在 Scene 视图中显示入口半径与出口连线。
    /// </summary>
    private void OnDrawGizmosSelected()
    {
        Gizmos.color = _enabled ? new Color(0.1f, 0.85f, 1f, 0.85f) : new Color(0.5f, 0.5f, 0.5f, 0.5f);
        Gizmos.DrawWireSphere(transform.position, TriggerRadius);

        if (_pairedPoint == null)
            return;

        Gizmos.color = new Color(1f, 0.85f, 0.15f, 0.85f);
        Gizmos.DrawLine(transform.position, _pairedPoint.transform.position);
    }
}
