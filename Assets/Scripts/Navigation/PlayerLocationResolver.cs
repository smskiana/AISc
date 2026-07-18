using UnityEngine;

/// <summary>
/// 解析并同步玩家当前所在的 SceneAnchor location_id。
/// </summary>
public class PlayerLocationResolver : MonoBehaviour
{
    [SerializeField] private float _resolveRadius = 2.5f;
    [SerializeField] private float _syncInterval = 0.2f;

    private float _syncTimer;
    private string _lastReportedLocationId;

    /// <summary>
    /// 按固定频率同步玩家当前地点。
    /// </summary>
    private void Update()
    {
        _syncTimer += Time.deltaTime;
        if (_syncTimer < _syncInterval)
            return;

        _syncTimer = 0f;
        SyncNow();
    }

    /// <summary>
    /// 立即解析当前位置，并在地点变化时同步给游戏状态与后端。
    /// </summary>
    public bool SyncNow(bool force = false)
    {
        var gameManager = GameManager.Instance;
        if (gameManager?.WS == null
            || !gameManager.WS.IsConnected
            || !gameManager.IsGameplayReady
            || gameManager.IsDialogueActive)
            return false;

        if (!SceneAnchorRegistry.TryResolveNearestLocation(transform.position, _resolveRadius, out var nearest))
            return false;

        if (nearest == null || string.IsNullOrWhiteSpace(nearest.LocationId))
            return false;

        if (!force && _lastReportedLocationId == nearest.LocationId)
            return true;

        _lastReportedLocationId = nearest.LocationId;
        gameManager.SendPlayerMove(nearest.LocationId);
        return true;
    }

    /// <summary>
    /// 在 Inspector 中约束地点解析参数。
    /// </summary>
    private void OnValidate()
    {
        _resolveRadius = Mathf.Max(0f, _resolveRadius);
        _syncInterval = Mathf.Max(0.05f, _syncInterval);
    }
}
