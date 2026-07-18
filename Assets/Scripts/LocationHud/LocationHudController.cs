using UnityEngine;

/// <summary>
/// 订阅玩家位置变化，并协调地点 Model 与 View。
/// </summary>
public sealed class LocationHudController : MonoBehaviour
{
    [SerializeField] private LocationHudView _view;

    private readonly LocationHudModel _model = new LocationHudModel();
    private GameManager _gameManager;

    /// <summary>
    /// 绑定 GameManager 的位置事件并渲染当前状态。
    /// </summary>
    private void Start()
    {
        _gameManager = GameManager.Instance;
        if (_gameManager == null)
            return;

        _gameManager.OnPlayerLocationChanged += HandleLocationChanged;
        HandleLocationChanged(_gameManager.PlayerLocation);
    }

    /// <summary>
    /// 更新地点 Model 后把面向玩家的显示名交给 View。
    /// </summary>
    private void HandleLocationChanged(string locationId)
    {
        _model.SetLocation(locationId);
        _view?.Render(_model.DisplayName);
    }

    /// <summary>
    /// 释放玩家位置事件订阅。
    /// </summary>
    private void OnDestroy()
    {
        if (_gameManager != null)
            _gameManager.OnPlayerLocationChanged -= HandleLocationChanged;
    }
}
