using System;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>
/// Unity → Python 通信客户端（原生 WebSocket）。
/// 保留 health 检查，但主消息链全部走持久 WS。
/// </summary>
public class WebSocketClient : MonoBehaviour
{
    public event Action<string> Disconnected;
    [SerializeField] private string _healthUrl = "http://127.0.0.1:8766/api/health";
    [SerializeField] private string _wsUrl = "ws://127.0.0.1:8766/ws";
    [SerializeField] private bool _autoConnectOnStart = false;

    public bool IsConnected { get; private set; }
    public bool IsConnecting { get; private set; }
    public bool HasConnectAttemptFinished { get; private set; }
    public string LastConnectionError { get; private set; }
    public string HealthUrl => _healthUrl;
    public string WebSocketUrl => _wsUrl;
    public Callbacks Callbacks { get; set; } = new Callbacks();
    public ProtocolClient Protocol { get; } = new ProtocolClient();
    private const int ConversationDiagnosticCapacity = 50;
    private readonly List<ConversationRetrievalDiagnosticSnapshot> _conversationDiagnostics = new();
    private const int MemoryDiagnosticCapacity = 100;
    private readonly List<MemoryRetrievalDiagnosticSnapshot> _memoryDiagnostics = new();

    private ClientWebSocket _socket;
    private CancellationTokenSource _cts;
    private readonly SemaphoreSlim _sendLock = new(1, 1);
    private readonly ConcurrentQueue<string> _incomingMessages = new();
    private readonly ConcurrentQueue<PendingLog> _pendingLogs = new();
    private bool _isShuttingDown;
    private Coroutine _connectRoutine;
    private bool _wasConnected;

    private struct PendingLog
    {
        public LogType Type;
        public string Message;
    }

    void Start()
    {
        if (_autoConnectOnStart)
            BeginConnect();
    }

    /// <summary>
    /// 显式触发连接流程；用于开始界面在后端健康后发起连接或重试。
    /// </summary>
    public void BeginConnect(bool forceRetry = false)
    {
        if (IsConnected) return;
        if (_connectRoutine != null && !forceRetry) return;

        if (_connectRoutine != null)
        {
            StopCoroutine(_connectRoutine);
            _connectRoutine = null;
        }

        LastConnectionError = null;
        HasConnectAttemptFinished = false;
        IsConnecting = true;
        _connectRoutine = StartCoroutine(CheckHealthThenConnect());
    }

    void Update()
    {
        DrainPendingLogs();
        DrainIncomingMessages();
        if (IsConnected)
        {
            _wasConnected = true;
        }
        else if (_wasConnected && !_isShuttingDown)
        {
            _wasConnected = false;
            Disconnected?.Invoke(string.IsNullOrWhiteSpace(LastConnectionError) ? "连接关闭" : LastConnectionError);
        }
    }

    IEnumerator CheckHealthThenConnect()
    {
        using var req = UnityWebRequest.Get(_healthUrl);
        yield return req.SendWebRequest();
        if (req.result == UnityWebRequest.Result.Success)
        {
            Debug.Log($"[WS] 健康检查通过: {req.downloadHandler.text}");
            yield return ConnectWebSocket();
        }
        else
        {
            LastConnectionError = req.error;
            HasConnectAttemptFinished = true;
            IsConnecting = false;
            _connectRoutine = null;
            Debug.LogError($"[WS] 无法连接到服务器: {req.error}");
        }
    }

    /// <summary>
    /// 建立 WebSocket 长连接，并启动后台接收循环。
    /// </summary>
    IEnumerator ConnectWebSocket()
    {
        var task = ConnectAsync();
        while (!task.IsCompleted)
        {
            yield return null;
        }

        if (task.Exception != null)
        {
            LastConnectionError = task.Exception.GetBaseException().Message;
            IsConnecting = false;
            _connectRoutine = null;
            Debug.LogError($"[WS] 建连失败: {task.Exception.GetBaseException().Message}");
        }
    }

    /// <summary>
    /// 发送文本消息到后端。
    /// </summary>
    public void Send(string json)
    {
        if (!IsConnected || _socket == null || _socket.State != WebSocketState.Open)
        {
            Debug.LogWarning($"[WS] 未连接，丢弃消息: {json}");
            return;
        }

        _ = SendAsync(json);
    }

    async Task ConnectAsync()
    {
        LastConnectionError = null;
        try
        {
            _cts = new CancellationTokenSource();
            _socket = new ClientWebSocket();
            await _socket.ConnectAsync(new Uri(_wsUrl), _cts.Token);
            IsConnected = true;
            EnqueueLog(LogType.Log, $"[WS] 已连接: {_wsUrl}");
            _ = Task.Run(() => ReceiveLoopAsync(_cts.Token));
            Protocol.BeginSession();
            Send(Protocol.CreateHello($"req_{Guid.NewGuid():N}"));
        }
        catch (Exception e)
        {
            LastConnectionError = e.Message;
            throw;
        }
        finally
        {
            IsConnecting = false;
            HasConnectAttemptFinished = true;
            _connectRoutine = null;
        }
    }

    /// <summary>
    /// 后台接收循环：只负责收包与排队，真正分发留在主线程。
    /// </summary>
    async Task ReceiveLoopAsync(CancellationToken token)
    {
        var buffer = new byte[8192];

        try
        {
            while (!token.IsCancellationRequested && _socket != null && _socket.State == WebSocketState.Open)
            {
                using var stream = new MemoryStream();
                WebSocketReceiveResult result;

                do
                {
                    result = await _socket.ReceiveAsync(new ArraySegment<byte>(buffer), token);

                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        await CloseSocketAsync();
                        EnqueueLog(LogType.Log, "[WS] 连接已关闭");
                        return;
                    }

                    stream.Write(buffer, 0, result.Count);
                }
                while (!result.EndOfMessage);

                var message = Encoding.UTF8.GetString(stream.ToArray());
                _incomingMessages.Enqueue(message);
            }
        }
        catch (OperationCanceledException)
        {
        }
        catch (Exception e)
        {
            if (!_isShuttingDown)
            {
                EnqueueLog(LogType.Error, $"[WS] 接收循环异常: {e.Message}");
            }
            IsConnected = false;
            IsConnecting = false;
        }
    }

    async Task SendAsync(string json)
    {
        await _sendLock.WaitAsync();
        try
        {
            if (_socket == null || _socket.State != WebSocketState.Open)
                return;

            byte[] body = Encoding.UTF8.GetBytes(json);
            await _socket.SendAsync(
                new ArraySegment<byte>(body),
                WebSocketMessageType.Text,
                true,
                _cts != null ? _cts.Token : CancellationToken.None);
            EnqueueLog(LogType.Log, $"[WS] → {json.Substring(0, Math.Min(json.Length, 160))}");
        }
        catch (Exception e)
        {
            EnqueueLog(LogType.Error, $"[WS] 发送失败: {e.Message}");
        }
        finally
        {
            _sendLock.Release();
        }
    }

    void DrainIncomingMessages()
    {
        while (_incomingMessages.TryDequeue(out var json))
        {
            try
            {
                if (Protocol.TryConsumeControlMessage(json))
                {
                    Debug.Log($"[Protocol] 握手状态: negotiated={Protocol.IsNegotiated}, session={Protocol.SessionId}");
                    continue;
                }
                var msg = JsonUtility.FromJson<SimpleMsg>(json);
                if (msg?.type == "DIALOGUE_RETRIEVAL_DIAGNOSTIC")
                {
                    RecordConversationDiagnostic(JsonUtility.FromJson<ConversationRetrievalDiagnosticSnapshot>(json));
                    continue;
                }
                if (msg?.type == "MEMORY_RETRIEVAL_DIAGNOSTIC")
                {
                    RecordMemoryDiagnostic(JsonUtility.FromJson<MemoryRetrievalDiagnosticSnapshot>(json));
                    continue;
                }
                if (!string.IsNullOrEmpty(msg?.type))
                {
                    Debug.Log($"[WS] ← {msg.type}");
                }
                MessageRouter.Dispatch(json, Callbacks);
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[WS] 消息分发失败: {e.Message}\n{json}");
            }
        }
    }

    /// <summary>
    /// 返回最近会话检索诊断，可按 conversation_id 和 speaker_id 过滤。
    /// </summary>
    public List<ConversationRetrievalDiagnosticSnapshot> GetConversationDiagnostics(
        string conversationId = null,
        string speakerId = null)
    {
        return _conversationDiagnostics.FindAll(item =>
            (string.IsNullOrWhiteSpace(conversationId) || item.conversation_id == conversationId) &&
            (string.IsNullOrWhiteSpace(speakerId) || item.speaker_id == speakerId));
    }

    /// <summary>
    /// 返回 WebSocket 最近收到的通用记忆检索诊断。
    /// </summary>
    public List<MemoryRetrievalDiagnosticSnapshot> GetMemoryDiagnostics(
        string retrievalTraceId = null,
        string npcId = null,
        string mode = null,
        string strategy = null)
    {
        return _memoryDiagnostics.FindAll(item =>
            (string.IsNullOrWhiteSpace(retrievalTraceId) || item.retrieval_trace_id == retrievalTraceId) &&
            (string.IsNullOrWhiteSpace(npcId) || item.npc_id == npcId) &&
            (string.IsNullOrWhiteSpace(mode) || item.mode == mode) &&
            (string.IsNullOrWhiteSpace(strategy) || item.strategy == strategy));
    }

    /// <summary>
    /// 用固定容量缓存后端逐轮检索诊断，避免运行时间增长导致内存无界。
    /// </summary>
    private void RecordConversationDiagnostic(ConversationRetrievalDiagnosticSnapshot snapshot)
    {
        if (snapshot == null || string.IsNullOrWhiteSpace(snapshot.conversation_id))
            return;
        if (_conversationDiagnostics.Count >= ConversationDiagnosticCapacity)
            _conversationDiagnostics.RemoveAt(0);
        _conversationDiagnostics.Add(snapshot);
    }

    /// <summary>
    /// 用固定容量缓存通用记忆检索诊断，避免运行时间增长导致内存无界。
    /// </summary>
    private void RecordMemoryDiagnostic(MemoryRetrievalDiagnosticSnapshot snapshot)
    {
        if (snapshot == null || string.IsNullOrWhiteSpace(snapshot.retrieval_trace_id))
            return;
        if (_memoryDiagnostics.Count >= MemoryDiagnosticCapacity)
            _memoryDiagnostics.RemoveAt(0);
        _memoryDiagnostics.Add(snapshot);
    }

    void DrainPendingLogs()
    {
        while (_pendingLogs.TryDequeue(out var pending))
        {
            switch (pending.Type)
            {
                case LogType.Error:
                    Debug.LogError(pending.Message);
                    break;
                case LogType.Warning:
                    Debug.LogWarning(pending.Message);
                    break;
                default:
                    Debug.Log(pending.Message);
                    break;
            }
        }
    }

    void EnqueueLog(LogType type, string message)
    {
        _pendingLogs.Enqueue(new PendingLog
        {
            Type = type,
            Message = message,
        });
    }

    async Task CloseSocketAsync()
    {
        IsConnected = false;
        if (_socket == null) return;

        try
        {
            if (_socket.State == WebSocketState.Open || _socket.State == WebSocketState.CloseReceived)
            {
                await _socket.CloseAsync(
                    WebSocketCloseStatus.NormalClosure,
                    "Unity closing",
                    CancellationToken.None);
            }
        }
        catch
        {
        }
        finally
        {
            _socket.Dispose();
            _socket = null;
        }
    }

    async Task ShutdownAsync()
    {
        _isShuttingDown = true;
        IsConnected = false;
        IsConnecting = false;

        if (_cts != null)
        {
            _cts.Cancel();
            _cts.Dispose();
            _cts = null;
        }

        await CloseSocketAsync();
    }

    void OnDestroy()
    {
        StopAllCoroutines();
        _connectRoutine = null;
        _ = ShutdownAsync();
    }
}
