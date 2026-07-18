using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 协调存档产品操作、确认弹窗、截图和现有双端事务服务。
/// </summary>
public sealed class SaveManagementController : MonoBehaviour
{
    public static SaveManagementController Instance { get; private set; }

    [SerializeField] private SaveManagementView _view;
    [SerializeField] private SaveScreenshotCapture _screenshotCapture;

    public bool IsOpen { get; private set; }
    public event Action Closed;

    private UnitySaveService _saveService;
    private PauseController _pauseController;
    private List<SaveInfo> _saves = new List<SaveInfo>();
    private int _selectedIndex = -1;
    private bool _saveMode;

    /// <summary>
    /// 建立全局存档管理入口。
    /// </summary>
    private void Awake()
    {
        Instance = this;
    }

    /// <summary>
    /// 绑定存档服务事件和固定 UI 命令。
    /// </summary>
    private void Start()
    {
        _saveService = GameManager.Instance?.SaveService;
        _pauseController = PauseController.Instance;
        _view?.Bind(CreateNew, RequestOverwrite, RenameSelected, RequestDelete, RequestLoad, Close);
        if (_saveService != null)
        {
            _saveService.SaveFinished += HandleSaveFinished;
            _saveService.LoadFinished += HandleLoadFinished;
            _saveService.DeleteFinished += HandleDeleteFinished;
            _saveService.OperationFailed += HandleOperationFailed;
        }
        _view?.SetVisible(false, true);
    }

    /// <summary>
    /// 打开保存或加载模式并刷新有效槽位列表。
    /// </summary>
    public void Open(bool saveMode, string prefilledName = null)
    {
        if (_saveService == null)
            return;
        IsOpen = true;
        _saveMode = saveMode;
        _selectedIndex = -1;
        Refresh();
        _view?.SetVisible(true, saveMode);
        if (saveMode)
            _view?.SetNameInput(prefilledName ?? _saveService.CreateDefaultManualName());
        _pauseController?.RequestPause(PauseSources.SaveManagement);
    }

    /// <summary>
    /// 关闭面板并只释放存档管理暂停来源。
    /// </summary>
    public void Close()
    {
        if (!IsOpen) return;
        IsOpen = false;
        _view?.SetVisible(false, _saveMode);
        _pauseController?.ReleasePause(PauseSources.SaveManagement);
        Closed?.Invoke();
    }

    /// <summary>
    /// 新建无限手动槽并启动双端保存。
    /// </summary>
    private void CreateNew()
    {
        string displayName = _view?.NameInput;
        if (!ValidateManualName(displayName, null)) return;
        BeginSave(_saveService.CreateManualSlotId(), displayName, false);
    }

    /// <summary>
    /// 请求二次确认后覆盖当前手动槽。
    /// </summary>
    private void RequestOverwrite()
    {
        SaveInfo selected = SelectedSave;
        if (selected == null || selected.is_auto) return;
        SystemMessageController.Instance?.ShowBlocking(
            $"确定覆盖“{selected.display_name}”吗？",
            "覆盖",
            () => BeginSave(selected.slot, selected.display_name, false),
            "取消");
    }

    /// <summary>
    /// 使用输入框内容重命名当前手动槽。
    /// </summary>
    private void RenameSelected()
    {
        SaveInfo selected = SelectedSave;
        string displayName = _view?.NameInput;
        if (selected == null || selected.is_auto || !ValidateManualName(displayName, selected.slot)) return;
        try
        {
            _saveService.Rename(selected.slot, displayName);
            Refresh();
        }
        catch (Exception error)
        {
            SystemMessageController.Instance?.ShowBlocking(error.Message, "确定", null);
        }
    }

    /// <summary>
    /// 请求二次确认后删除当前手动槽。
    /// </summary>
    private void RequestDelete()
    {
        SaveInfo selected = SelectedSave;
        if (selected == null || selected.is_auto) return;
        SystemMessageController.Instance?.ShowBlocking(
            $"确定删除“{selected.display_name}”吗？此操作无法撤销。",
            "删除",
            () =>
            {
                SystemMessageController.Instance?.SetLoading(true, "正在删除存档...");
                _saveService.Delete(selected.slot);
            },
            "取消");
    }

    /// <summary>
    /// 加载前统一确认当前未保存进度将被丢弃。
    /// </summary>
    private void RequestLoad()
    {
        SaveInfo selected = SelectedSave;
        if (selected == null) return;
        SystemMessageController.Instance?.ShowBlocking(
            $"加载“{selected.display_name}”会丢失当前未保存进度。是否继续？",
            "加载",
            () =>
            {
                SystemMessageController.Instance?.SetLoading(true, "正在加载存档...");
                _saveService.Load(selected.slot);
            },
            "取消");
    }

    /// <summary>
    /// 抓取世界截图并调用现有双端保存事务。
    /// </summary>
    private void BeginSave(string slotId, string displayName, bool isAuto)
    {
        byte[] screenshot = _screenshotCapture?.CapturePng();
        SystemMessageController.Instance?.SetLoading(true, "正在保存游戏...");
        _saveService.Save(slotId, displayName, isAuto, screenshot);
    }

    /// <summary>
    /// 校验手动存档名非空且不与其他槽重复。
    /// </summary>
    private bool ValidateManualName(string displayName, string currentSlot)
    {
        if (string.IsNullOrWhiteSpace(displayName))
        {
            SystemMessageController.Instance?.ShowBlocking("存档名不能为空。", "确定", null);
            return false;
        }
        if (_saves.Exists(save => save.slot != currentSlot
            && string.Equals(save.display_name, displayName.Trim(), StringComparison.Ordinal)))
        {
            SystemMessageController.Instance?.ShowBlocking("手动存档名称不得重复。", "确定", null);
            return false;
        }
        return true;
    }

    /// <summary>
    /// 重新读取有效槽位并重建列表。
    /// </summary>
    private void Refresh()
    {
        _saves = _saveService?.ListSaves() ?? new List<SaveInfo>();
        _view?.Render(_saves, Select);
    }

    /// <summary>
    /// 选中列表项并把名称带入输入框。
    /// </summary>
    private void Select(int index)
    {
        if (index < 0 || index >= _saves.Count) return;
        _selectedIndex = index;
        _view?.SetSelected(index);
        _view?.SetNameInput(_saves[index].display_name);
    }

    private SaveInfo SelectedSave => _selectedIndex >= 0 && _selectedIndex < _saves.Count ? _saves[_selectedIndex] : null;

    /// <summary>
    /// 保存完成后关闭遮罩、刷新列表并显示三秒普通提醒。
    /// </summary>
    private void HandleSaveFinished(string slot, bool success, string detail)
    {
        SystemMessageController.Instance?.SetLoading(false);
        if (success)
        {
            Refresh();
            SystemMessageController.Instance?.ShowNotice("保存成功");
        }
        else
        {
            SystemMessageController.Instance?.ShowBlocking($"保存失败：{detail}", "确定", null);
        }
    }

    /// <summary>
    /// 读档成功后关闭遮罩和存档面板，不额外显示普通提醒。
    /// </summary>
    private void HandleLoadFinished(GameSaveData data, string checkpointId)
    {
        SystemMessageController.Instance?.SetLoading(false);
        Close();
    }

    /// <summary>
    /// 删除完成后关闭遮罩并刷新列表。
    /// </summary>
    private void HandleDeleteFinished(string slot, bool success, string detail)
    {
        SystemMessageController.Instance?.SetLoading(false);
        if (success) Refresh();
        else SystemMessageController.Instance?.ShowBlocking($"删除失败：{detail}", "确定", null);
    }

    /// <summary>
    /// 收口普通加载或存档事务异常，并保持当前世界不变。
    /// </summary>
    private void HandleOperationFailed(string detail)
    {
        SystemMessageController.Instance?.SetLoading(false);
        SystemMessageController.Instance?.ShowBlocking($"操作失败：{detail}", "确定", null);
    }

    /// <summary>
    /// 释放存档服务事件订阅和暂停来源。
    /// </summary>
    private void OnDestroy()
    {
        if (Instance == this) Instance = null;
        if (_saveService != null)
        {
            _saveService.SaveFinished -= HandleSaveFinished;
            _saveService.LoadFinished -= HandleLoadFinished;
            _saveService.DeleteFinished -= HandleDeleteFinished;
            _saveService.OperationFailed -= HandleOperationFailed;
        }
        _pauseController?.ReleasePause(PauseSources.SaveManagement);
    }
}
