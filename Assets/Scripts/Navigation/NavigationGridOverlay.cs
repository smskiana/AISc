using UnityEngine;

/// <summary>
/// 在场景中渲染导航网格调试覆盖图。
/// </summary>
[RequireComponent(typeof(SpriteRenderer))]
public class NavigationGridOverlay : MonoBehaviour
{
    [SerializeField] private NavigationGridAsset _navigationGrid;
    [SerializeField] private bool _rebuildOnStart = true;
    [SerializeField] private int _sortingOrder = 100;
    [SerializeField] private Color _walkableColor = new(0.1f, 0.9f, 0.35f, 0.25f);
    [SerializeField] private Color _blockedColor = new(0.95f, 0.15f, 0.1f, 0.35f);
    [SerializeField] private Color _teleportEntranceColor = new(0.1f, 0.45f, 1f, 0.9f);
    [SerializeField] private Color _teleportExitColor = new(1f, 0.9f, 0.1f, 0.9f);

    private SpriteRenderer _spriteRenderer;
    private Texture2D _debugTexture;
    private Sprite _debugSprite;

    /// <summary>
    /// 初始化覆盖图引用，并按配置刷新一次网格显示。
    /// </summary>
    private void Awake()
    {
        _spriteRenderer = GetComponent<SpriteRenderer>();
        _spriteRenderer.sortingOrder = _sortingOrder;

        if (_rebuildOnStart)
            RebuildOverlay();
    }

    /// <summary>
    /// 根据 NavigationGridAsset 重新生成调试 Sprite。
    /// </summary>
    [ContextMenu("Rebuild Navigation Overlay")]
    public void RebuildOverlay()
    {
        if (_navigationGrid == null)
        {
            Debug.LogWarning("[NavigationGridOverlay] 未配置 NavigationGridAsset");
            return;
        }

        _debugTexture = _navigationGrid.BuildDebugTexture(
            _walkableColor,
            _blockedColor,
            _teleportEntranceColor,
            _teleportExitColor);

        if (_debugTexture == null)
        {
            Debug.LogWarning("[NavigationGridOverlay] 调试纹理生成失败");
            return;
        }

        float pixelsPerUnit = 1f / Mathf.Max(0.01f, _navigationGrid.CellSize);
        _debugSprite = Sprite.Create(
            _debugTexture,
            new Rect(0, 0, _debugTexture.width, _debugTexture.height),
            Vector2.zero,
            pixelsPerUnit);

        _spriteRenderer = _spriteRenderer != null ? _spriteRenderer : GetComponent<SpriteRenderer>();
        _spriteRenderer.sprite = _debugSprite;
        _spriteRenderer.sortingOrder = _sortingOrder;
        transform.position = new Vector3(
            _navigationGrid.WorldOrigin.x,
            _navigationGrid.WorldOrigin.y,
            transform.position.z);
    }

    /// <summary>
    /// 编辑器中修改排序层级时同步到 SpriteRenderer。
    /// </summary>
    private void OnValidate()
    {
        if (_spriteRenderer == null)
            _spriteRenderer = GetComponent<SpriteRenderer>();

        if (_spriteRenderer != null)
            _spriteRenderer.sortingOrder = _sortingOrder;
    }
}
