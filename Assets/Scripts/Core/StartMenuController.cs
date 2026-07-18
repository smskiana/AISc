using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 开始界面控制器：负责后端启动、连接状态、登录名和存档入口。
/// 当前工程尚未落真实账号系统，因此“登录”只记录本地玩家名。
/// </summary>
public class StartMenuController : MonoBehaviour
{
    private const string PlayerNameKey = "player_display_name";
    private const string DefaultPlayerName = "小李";

    [SerializeField] private StartMenuView _view;

    private Coroutine _bootstrapRoutine;
    private bool _hasRequestedSaves;
    private bool _isStartingGame;
    private bool _openQuickSaveAfterGameReady;
    private string _quickSaveDefaultName;

    /// <summary>
    /// 初始化开始界面，并默认按需拉起本机后端。
    /// </summary>
    private void Start()
    {
        if (_view == null)
        {
            Debug.LogError("[StartMenu] 未绑定 StartMenuView，无法启动开始界面。");
            return;
        }

        _view.BindStaticActions(
            OnLoginClicked,
            OnRetryBackendClicked,
            OnRefreshSavesClicked,
            OnNewGameClicked,
            OnQuitDesktopClicked);
        BindGameManagerEvents();
        LoadLocalPlayerName();
        BeginBootstrap(forceLaunch: true);
    }

    /// <summary>
    /// 解除事件绑定；退出 Play 或应用关闭时回收本轮前端拉起的后端。
    /// </summary>
    private void OnDestroy()
    {
        UnbindGameManagerEvents();
        StartMenuBackendLauncher.ShutdownOwnedBackend();
    }

    /// <summary>
    /// 应用退出时确保 owned 后端进程不会继续空跑。
    /// </summary>
    private void OnApplicationQuit()
    {
        StartMenuBackendLauncher.ShutdownOwnedBackend();
    }

    /// <summary>
    /// 手动或自动开始“检查后端 → 连接 WS → 读取存档”的启动链。
    /// </summary>
    private void BeginBootstrap(bool forceLaunch)
    {
        if (_bootstrapRoutine != null)
            StopCoroutine(_bootstrapRoutine);

        _bootstrapRoutine = StartCoroutine(BootstrapRoutine(forceLaunch));
    }

    private IEnumerator BootstrapRoutine(bool forceLaunch)
    {
        var gm = GameManager.Instance;
        if (gm == null)
        {
            _view.SetStatus("未找到 GameManager，无法启动开始界面。");
            _view.SetButtonsInteractable(partial: true);
            yield break;
        }

        _view.SetButtonsInteractable(false);
        _view.SetStatus("正在检查后端状态...");

        bool isHealthy = false;
        yield return StartMenuBackendLauncher.CheckHealth(gm.WS.HealthUrl, result => isHealthy = result);

        if (!isHealthy && forceLaunch)
        {
            if (!StartMenuBackendLauncher.TryLaunchBackend())
            {
                _view.SetStatus("后端未运行，且自动启动失败。请检查本机 Python 环境。");
                _view.SetButtonsInteractable(partial: true);
                yield break;
            }
        }
        else if (!isHealthy)
        {
            _view.SetStatus("后端未启动。可点击“启动后端并连接”。");
            _view.SetButtonsInteractable(partial: true);
            yield break;
        }

        if (!isHealthy)
        {
            _view.SetStatus("正在等待后端启动...");
            bool becameHealthy = false;
            yield return StartMenuBackendLauncher.WaitForHealth(gm.WS.HealthUrl, 20f, result => becameHealthy = result);
            isHealthy = becameHealthy;
        }

        if (!isHealthy)
        {
            _view.SetStatus("后端仍未就绪。你可以再次尝试启动。");
            _view.SetButtonsInteractable(partial: true);
            yield break;
        }

        _view.SetStatus("后端在线，正在连接游戏服务...");
        gm.WS.BeginConnect(forceRetry: true);
        yield return new WaitUntil(() => gm.WS.IsConnected || gm.WS.HasConnectAttemptFinished);

        if (!gm.WS.IsConnected)
        {
            _view.SetStatus($"连接失败：{gm.WS.LastConnectionError}");
            _view.SetButtonsInteractable(partial: true);
            yield break;
        }

        _view.SetStatus("连接成功，正在读取存档列表...");
        _hasRequestedSaves = true;
        gm.RequestSavesList();
        _view.SetButtonsInteractable(partial: true);
    }

    /// <summary>
    /// 绑定 GameManager 事件，接收存档列表、错误和进场完成通知。
    /// </summary>
    private void BindGameManagerEvents()
    {
        var gm = GameManager.Instance;
        if (gm == null) return;

        gm.OnSavesList += HandleSavesList;
        gm.OnGameError += HandleGameError;
        gm.OnGameReady += HandleGameReady;
        gm.OnLoadComplete += HandleLoadComplete;
        if (gm.SaveService != null)
            gm.SaveService.NewGameStorageResetFinished += HandleNewGameStorageResetFinished;
    }

    private void UnbindGameManagerEvents()
    {
        var gm = GameManager.Instance;
        if (gm == null) return;

        gm.OnSavesList -= HandleSavesList;
        gm.OnGameError -= HandleGameError;
        gm.OnGameReady -= HandleGameReady;
        gm.OnLoadComplete -= HandleLoadComplete;
        if (gm.SaveService != null)
            gm.SaveService.NewGameStorageResetFinished -= HandleNewGameStorageResetFinished;
    }

    private void HandleSavesList(SavesListMsg msg)
    {
        _view.RenderSaveList(msg?.saves, _hasRequestedSaves, OnLoadSlotClicked);
        _view.SetStatus("请选择新游戏或载入存档。");
    }

    private void HandleGameError(GameErrorMsg msg)
    {
        if (_isStartingGame)
            _view.SetStatus($"进入失败：{msg.message}");
        else
            _view.SetStatus($"服务提示：{msg.message}");

        _isStartingGame = false;
        SystemMessageController.Instance?.SetLoading(false);
        _view.SetButtonsInteractable(partial: true);
    }

    private void HandleLoadComplete(LoadCompleteMsg msg)
    {
        _view.SetStatus($"存档已读取：Day {msg.game_time.day}，正在进入街区...");
    }

    private void HandleGameReady(GameReadyMsg msg)
    {
        _isStartingGame = false;
        _view.SetVisible(false);
        if (_openQuickSaveAfterGameReady)
        {
            _openQuickSaveAfterGameReady = false;
            SaveManagementController.Instance?.Open(true, _quickSaveDefaultName);
        }
    }

    /// <summary>
    /// 从本地偏好读取玩家显示名。
    /// </summary>
    private void LoadLocalPlayerName()
    {
        _view.SetPlayerName(PlayerPrefs.GetString(PlayerNameKey, DefaultPlayerName));
    }

    private void SaveLocalPlayerName()
    {
        string playerName = _view.GetPlayerName();
        PlayerPrefs.SetString(PlayerNameKey, playerName);
        PlayerPrefs.Save();
        _view.SetStatus($"已记录本地玩家名：{playerName}（当前后端对白仍使用默认称呼）。");
    }

    private void OnLoginClicked()
    {
        SaveLocalPlayerName();
    }

    private void OnRetryBackendClicked()
    {
        _view.SetStatus("正在尝试启动后端并重新连接...");
        BeginBootstrap(forceLaunch: true);
    }

    private void OnRefreshSavesClicked()
    {
        var gm = GameManager.Instance;
        if (gm == null || gm.WS == null || !gm.WS.IsConnected)
        {
            _view.SetStatus("当前未连接后端，无法刷新存档。");
            return;
        }

        _view.SetStatus("正在刷新存档列表...");
        gm.RequestSavesList();
    }

    private void OnNewGameClicked()
    {
        var gm = GameManager.Instance;
        if (gm == null || gm.WS == null || !gm.WS.IsConnected)
        {
            _view.SetStatus("尚未连接后端，无法开始新游戏。");
            return;
        }

        string defaultName = gm.SaveService?.CreateDefaultManualName();
        if (SystemMessageController.Instance == null)
        {
            BeginNewGame(false, defaultName);
            return;
        }

        SystemMessageController.Instance.ShowBlocking(
            "新游戏可以先快速创建手动存档，也可以无存档进入。",
            "快速创建",
            () => BeginNewGame(true, defaultName),
            "无视，继续进入",
            () => BeginNewGame(false, defaultName));
    }

    /// <summary>
    /// 根据新游戏提醒选择启动世界，并可在进场后打开预填存档名的快速创建页。
    /// </summary>
    private void BeginNewGame(bool openQuickSave, string defaultName)
    {
        var gm = GameManager.Instance;
        if (gm == null) return;
        SaveLocalPlayerName();
        _openQuickSaveAfterGameReady = openQuickSave;
        _quickSaveDefaultName = defaultName;
        _isStartingGame = true;
        _view.SetButtonsInteractable(false);
        _view.SetStatus("正在永久清理全部存档与记忆检查点...");
        if (gm.SaveService == null)
        {
            HandleNewGameStorageResetFinished(false, "save_service_unavailable");
            return;
        }
        gm.SaveService.PurgeAllForNewGame();
    }

    /// <summary>
    /// 仅在双端存档均已清空后进入新游戏；失败时留在开始界面供玩家重试。
    /// </summary>
    private void HandleNewGameStorageResetFinished(bool succeeded, string reason)
    {
        if (!_isStartingGame) return;
        if (!succeeded)
        {
            _isStartingGame = false;
            _openQuickSaveAfterGameReady = false;
            _view.SetStatus($"新游戏存档清理失败：{reason}");
            _view.SetButtonsInteractable(partial: true);
            return;
        }

        _view.SetStatus("全部旧存档已永久删除，正在创建新游戏...");
        GameManager.Instance?.StartNewGameFlow();
    }

#if UNITY_EDITOR
    /// <summary>
    /// 供编辑器诊断控制钩子无存档启动新游戏，Player 构建不包含此入口。
    /// </summary>
    public bool StartNewGameForEditorDiagnostics()
    {
        var gm = GameManager.Instance;
        if (gm == null || gm.WS == null || !gm.WS.IsConnected)
            return false;

        string defaultName = gm.SaveService?.CreateDefaultManualName();
        BeginNewGame(false, defaultName);
        return true;
    }
#endif

    private void OnLoadSlotClicked(string slot)
    {
        var gm = GameManager.Instance;
        if (gm == null || gm.WS == null || !gm.WS.IsConnected)
        {
            _view.SetStatus("尚未连接后端，无法加载存档。");
            return;
        }

        SaveLocalPlayerName();
        _isStartingGame = true;
        _view.SetButtonsInteractable(false);
        _view.SetStatus($"正在加载存档 slot_{slot}...");
        gm.StartLoadFlow(slot);
    }

    /// <summary>
    /// 开始界面直接退出桌面，不再显示二次确认。
    /// </summary>
    private static void OnQuitDesktopClicked()
    {
#if UNITY_EDITOR
        UnityEditor.EditorApplication.isPlaying = false;
#else
        Application.Quit();
#endif
    }

#if UNITY_EDITOR
    /// <summary>
    /// 编辑器下自动补抓同物体或子物体上的 View，减少手工漏绑概率。
    /// </summary>
    private void OnValidate()
    {
        if (_view == null)
            _view = GetComponentInChildren<StartMenuView>(true);
    }
#endif
}
