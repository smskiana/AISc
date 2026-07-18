using UnityEngine;

/// <summary>
/// 编排游戏内暂停菜单、存档页面、返回开始菜单和退出桌面流程。
/// </summary>
public sealed class PauseMenuController : MonoBehaviour
{
    [SerializeField] private PauseMenuView _view;

    public bool IsOpen { get; private set; }

    private PauseController _pauseController;
    private UnitySaveService _saveService;
    private bool _settingsOpen;
    private bool _exitAfterSave;

    /// <summary>
    /// 绑定菜单按钮和存档事务事件。
    /// </summary>
    private void Start()
    {
        _pauseController = PauseController.Instance;
        _saveService = GameManager.Instance?.SaveService;
        _view?.Bind(RequestDirectExit, SaveAndExit, OpenSave, OpenLoad, OpenSettings, Close, RequestQuitDesktop);
        _view?.SetVisible(false);
        if (_saveService != null)
            _saveService.SaveFinished += HandleSaveFinished;
        if (SaveManagementController.Instance != null)
            SaveManagementController.Instance.Closed += HandleSaveManagementClosed;
    }

    /// <summary>
    /// 使用 Esc 打开、关闭或从设置页返回，阻塞弹窗与加载期间忽略 Esc。
    /// </summary>
    private void Update()
    {
        if (!Input.GetKeyDown(KeyCode.Escape))
            return;
        if (SystemMessageController.Instance != null
            && (SystemMessageController.Instance.IsBlocking || SystemMessageController.Instance.IsLoading))
            return;
        if (SaveManagementController.Instance != null && SaveManagementController.Instance.IsOpen)
            return;

        if (_settingsOpen)
        {
            _settingsOpen = false;
            _view?.ShowSettings(false);
        }
        else if (IsOpen)
        {
            Close();
        }
        else if (GameManager.Instance != null
            && GameManager.Instance.IsGameplayReady
            && (_pauseController == null || !_pauseController.IsPaused))
        {
            Open();
        }
    }

    /// <summary>
    /// 打开主菜单并申请暂停来源。
    /// </summary>
    public void Open()
    {
        if (IsOpen) return;
        IsOpen = true;
        _settingsOpen = false;
        _view?.SetVisible(true);
        _pauseController?.RequestPause(PauseSources.PauseMenu);
    }

    /// <summary>
    /// 关闭主菜单并只释放自身暂停来源。
    /// </summary>
    public void Close()
    {
        if (!IsOpen) return;
        IsOpen = false;
        _settingsOpen = false;
        _exitAfterSave = false;
        _view?.SetVisible(false);
        _pauseController?.ReleasePause(PauseSources.PauseMenu);
    }

    /// <summary>
    /// 打开保存管理页面。
    /// </summary>
    private void OpenSave()
    {
        _exitAfterSave = false;
        SaveManagementController.Instance?.Open(true);
    }

    /// <summary>
    /// 打开加载管理页面。
    /// </summary>
    private void OpenLoad()
    {
        _exitAfterSave = false;
        SaveManagementController.Instance?.Open(false);
    }

    /// <summary>
    /// 标记保存成功后返回开始菜单，并打开保存管理页面。
    /// </summary>
    private void SaveAndExit()
    {
        _exitAfterSave = true;
        SaveManagementController.Instance?.Open(true);
    }

    /// <summary>
    /// 显示设置占位页。
    /// </summary>
    private void OpenSettings()
    {
        _settingsOpen = true;
        _view?.ShowSettings(true);
    }

    /// <summary>
    /// 二次确认后不保存返回开始菜单。
    /// </summary>
    private void RequestDirectExit()
    {
        SystemMessageController.Instance?.ShowBlocking(
            "未保存的进度将丢失。确定返回开始菜单吗？",
            "直接退出",
            ReturnToStartMenu,
            "取消");
    }

    /// <summary>
    /// 二次确认后退出桌面。
    /// </summary>
    private void RequestQuitDesktop()
    {
        SystemMessageController.Instance?.ShowBlocking(
            "确定退出到桌面吗？",
            "退出",
            QuitDesktop,
            "取消");
    }

    /// <summary>
    /// 保存并退出成功时返回开始菜单；失败时提供继续退出或返回游戏。
    /// </summary>
    private void HandleSaveFinished(string slot, bool success, string detail)
    {
        if (!_exitAfterSave)
            return;
        if (success)
        {
            _exitAfterSave = false;
            ReturnToStartMenu();
        }
        else
        {
            SystemMessageController.Instance?.ShowBlocking(
                $"保存失败：{detail}",
                "仍然退出",
                ReturnToStartMenu,
                "返回游戏",
                () =>
                {
                    _exitAfterSave = false;
                    SaveManagementController.Instance?.Close();
                    Close();
                });
        }
    }

    /// <summary>
    /// 玩家关闭保存页但未保存时取消保存并退出意图。
    /// </summary>
    private void HandleSaveManagementClosed()
    {
        if (_exitAfterSave)
            _exitAfterSave = false;
    }

    /// <summary>
    /// 收口菜单状态并切回现有开始界面。
    /// </summary>
    private void ReturnToStartMenu()
    {
        SaveManagementController.Instance?.Close();
        Close();
        GameManager.Instance?.ReturnToStartMenu();
    }

    /// <summary>
    /// 在编辑器和正式构建中分别结束运行。
    /// </summary>
    private static void QuitDesktop()
    {
#if UNITY_EDITOR
        UnityEditor.EditorApplication.isPlaying = false;
#else
        Application.Quit();
#endif
    }

    /// <summary>
    /// 释放存档事件订阅和菜单暂停来源。
    /// </summary>
    private void OnDestroy()
    {
        if (_saveService != null)
            _saveService.SaveFinished -= HandleSaveFinished;
        if (SaveManagementController.Instance != null)
            SaveManagementController.Instance.Closed -= HandleSaveManagementClosed;
        _pauseController?.ReleasePause(PauseSources.PauseMenu);
    }
}
