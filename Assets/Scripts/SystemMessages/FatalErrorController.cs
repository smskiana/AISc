using UnityEngine;

/// <summary>
/// 收口后端断线和午夜结算失败等不可继续游戏的致命错误。
/// </summary>
public sealed class FatalErrorController : MonoBehaviour
{
    public static FatalErrorController Instance { get; private set; }

    private WebSocketClient _webSocket;
    private bool _shown;

    /// <summary>
    /// 建立全局致命错误入口并订阅连接断开事件。
    /// </summary>
    private void Start()
    {
        Instance = this;
        _webSocket = GameManager.Instance?.WS;
        if (_webSocket != null)
            _webSocket.Disconnected += HandleDisconnected;
    }

    /// <summary>
    /// 游戏进行中后端断线时禁止降级继续。
    /// </summary>
    private void HandleDisconnected(string reason)
    {
        if (GameManager.Instance != null && GameManager.Instance.IsGameplayReady)
            ShowFatal($"后端连接已断开：{reason}");
    }

    /// <summary>
    /// 显示只能退出桌面的致命错误阻塞弹窗。
    /// </summary>
    public void ShowFatal(string message)
    {
        if (_shown) return;
        _shown = true;
        if (SystemMessageController.Instance != null)
        {
            SystemMessageController.Instance.SetLoading(false);
            SystemMessageController.Instance.ShowBlocking(message, "退出到桌面", QuitDesktop);
        }
        else
        {
            Debug.LogError($"[Fatal] {message}");
            QuitDesktop();
        }
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
    /// 释放连接事件订阅和全局入口。
    /// </summary>
    private void OnDestroy()
    {
        if (_webSocket != null)
            _webSocket.Disconnected -= HandleDisconnected;
        if (Instance == this)
            Instance = null;
    }
}
