using UnityEngine;

/// <summary>
/// 让玩家复用场景 NavigationTeleportPoint，并响应靠近提示与传送输入。
/// </summary>
[RequireComponent(typeof(Rigidbody2D))]
[RequireComponent(typeof(PlayerLocationResolver))]
public class PlayerTeleportController : MonoBehaviour
{
    [SerializeField] private PlayerTransitionView _transitionView;
    [SerializeField] private KeyCode _interactionKey = KeyCode.F;
    [SerializeField] private float _teleportCooldown = 0.35f;

    private Rigidbody2D _rigidbody;
    private PlayerLocationResolver _locationResolver;
    private NavigationTeleportPoint[] _teleportPoints;
    private NavigationTeleportPoint _currentPoint;
    private float _cooldownRemaining;

    /// <summary>
    /// 缓存玩家依赖和当前场景中的传送端点。
    /// </summary>
    private void Awake()
    {
        _rigidbody = GetComponent<Rigidbody2D>();
        _locationResolver = GetComponent<PlayerLocationResolver>();
        _teleportPoints = FindObjectsOfType<NavigationTeleportPoint>(true);
        _transitionView?.Hide();
    }

    /// <summary>
    /// 根据游戏交互状态更新最近入口，并在按下交互键时传送。
    /// </summary>
    private void Update()
    {
        if (_cooldownRemaining > 0f)
            _cooldownRemaining -= Time.deltaTime;

        var gameManager = GameManager.Instance;
        bool canInteract = gameManager != null
            && gameManager.IsGameplayReady
            && !gameManager.IsDialogueActive
            && _cooldownRemaining <= 0f;

        if (!canInteract)
        {
            SetCurrentPoint(null);
            return;
        }

        SetCurrentPoint(FindNearestAvailablePoint());
        if (_currentPoint != null && Input.GetKeyDown(_interactionKey))
            Teleport(_currentPoint);
    }

    /// <summary>
    /// 查找触发半径内距离玩家最近且方向规则允许进入的端点。
    /// </summary>
    private NavigationTeleportPoint FindNearestAvailablePoint()
    {
        NavigationTeleportPoint nearest = null;
        float nearestSqrDistance = float.MaxValue;
        Vector2 playerPosition = transform.position;

        foreach (var point in _teleportPoints)
        {
            if (!CanEnter(point))
                continue;

            float sqrDistance = (point.WorldPosition - playerPosition).sqrMagnitude;
            float triggerRadius = point.TriggerRadius;
            if (sqrDistance > triggerRadius * triggerRadius || sqrDistance >= nearestSqrDistance)
                continue;

            nearest = point;
            nearestSqrDistance = sqrDistance;
        }

        return nearest;
    }

    /// <summary>
    /// 按传送点导出方向与双向规则判断当前端点能否作为玩家入口。
    /// </summary>
    private static bool CanEnter(NavigationTeleportPoint point)
    {
        if (point == null || !point.isActiveAndEnabled || !point.Enabled || point.PairedPoint == null)
            return false;

        if (point.ExportsLink)
            return true;

        var pairedPoint = point.PairedPoint;
        return pairedPoint.isActiveAndEnabled
            && pairedPoint.Enabled
            && pairedPoint.ExportsLink
            && pairedPoint.Bidirectional
            && pairedPoint.PairedPoint == point;
    }

    /// <summary>
    /// 将玩家移动到配对出口，并立即同步玩家 location_id。
    /// </summary>
    private void Teleport(NavigationTeleportPoint entrance)
    {
        var exit = entrance.PairedPoint;
        if (exit == null)
            return;

        _rigidbody.velocity = Vector2.zero;
        _rigidbody.position = exit.WorldPosition;
        transform.position = new Vector3(exit.WorldPosition.x, exit.WorldPosition.y, transform.position.z);
        Physics2D.SyncTransforms();

        _cooldownRemaining = Mathf.Max(0f, _teleportCooldown);
        SetCurrentPoint(null);
        _locationResolver.SyncNow(true);
    }

    /// <summary>
    /// 更新当前入口并驱动提示视图显隐。
    /// </summary>
    private void SetCurrentPoint(NavigationTeleportPoint point)
    {
        if (_currentPoint == point)
            return;

        _currentPoint = point;
        if (_transitionView == null)
            return;

        if (_currentPoint == null)
            _transitionView.Hide();
        else
            _transitionView.Show("按 F 前往");
    }

    /// <summary>
    /// 在 Inspector 中约束传送冷却参数。
    /// </summary>
    private void OnValidate()
    {
        _teleportCooldown = Mathf.Max(0f, _teleportCooldown);
    }
}
