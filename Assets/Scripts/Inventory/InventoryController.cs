using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 处理背包输入、暂停来源、只读渲染和存档桥接。
/// </summary>
public sealed class InventoryController : MonoBehaviour, IInventoryPersistence
{
    [SerializeField] private InventoryView _view;

    public bool IsOpen { get; private set; }

    private ItemCatalog _catalog;
    private InventoryModel _model;
    private PauseController _pauseController;

    /// <summary>
    /// 加载共享物品配置并建立初始空背包。
    /// </summary>
    private void Awake()
    {
        _catalog = new ItemCatalog();
        _catalog.Load();
        _model = new InventoryModel(_catalog);
        _pauseController = GetComponent<PauseController>();
        _view?.SetVisible(false);
    }

    /// <summary>
    /// 使用 B 打开或关闭，使用 Esc 仅关闭已打开的背包。
    /// </summary>
    private void Update()
    {
        if (Input.GetKeyDown(KeyCode.B))
        {
            if (IsOpen)
                Close();
            else
                Open();
        }
        else if (IsOpen && Input.GetKeyDown(KeyCode.Escape))
        {
            Close();
        }
    }

    /// <summary>
    /// 在没有其他阻塞暂停来源时打开并渲染背包。
    /// </summary>
    public void Open()
    {
        if (IsOpen || (_pauseController != null && _pauseController.IsPaused))
            return;
        IsOpen = true;
        _view?.Render(_model.CreateDisplayEntries());
        _view?.SetVisible(true);
        _pauseController?.RequestPause(PauseSources.Inventory);
    }

    /// <summary>
    /// 关闭背包并仅释放背包自己的暂停来源。
    /// </summary>
    public void Close()
    {
        if (!IsOpen)
            return;
        IsOpen = false;
        _view?.SetVisible(false);
        _pauseController?.ReleasePause(PauseSources.Inventory);
    }

    /// <summary>
    /// 导出背包存档快照。
    /// </summary>
    public List<InventoryEntrySaveData> CaptureInventory()
    {
        return _model.CreateSaveEntries();
    }

    /// <summary>
    /// 用读档结果覆盖背包并在打开状态下刷新界面。
    /// </summary>
    public void RestoreInventory(IEnumerable<InventoryEntrySaveData> entries)
    {
        _model.Restore(entries);
        if (IsOpen)
            _view?.Render(_model.CreateDisplayEntries());
    }
}
