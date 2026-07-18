using System;
using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

/// <summary>
/// 管理 Unity 侧协议 session、sequence、envelope 编解码和握手。
/// </summary>
public class ProtocolClient
{
    public const int SupportedVersion = 1;

    public string SessionId { get; private set; }
    public string LastProtocolError { get; private set; }
    public bool IsNegotiated { get; private set; }

    private long _nextSendSequence;
    private long _lastReceivedSequence;
    private const int TraceCapacity = 200;
    private readonly Queue<ProtocolTraceEntry> _trace = new();
    public event Action<ProtocolEnvelope> EnvelopeReceived;

    /// <summary>
    /// 为新 WebSocket 连接重置协议会话。
    /// </summary>
    public void BeginSession()
    {
        SessionId = null;
        LastProtocolError = null;
        IsNegotiated = false;
        _nextSendSequence = 1;
        _lastReceivedSequence = 0;
        _trace.Clear();
    }

    /// <summary>
    /// 构造连接后的 hello 握手 envelope。
    /// </summary>
    public string CreateHello(string requestId)
    {
        return CreateEnvelope("hello", requestId, new JObject
        {
            ["client_role"] = "unity_game",
            ["supported_protocol_versions"] = new JArray(SupportedVersion),
        });
    }

    /// <summary>
    /// 构造带版本、session 和 sequence 的协议 envelope。
    /// </summary>
    public string CreateEnvelope(string type, string requestId, JObject payload)
    {
        var envelope = new ProtocolEnvelope
        {
            protocol_version = SupportedVersion,
            type = type,
            request_id = requestId ?? string.Empty,
            session_id = SessionId ?? string.Empty,
            sequence = _nextSendSequence++,
            sent_at = DateTime.UtcNow.ToString("O"),
            payload = payload ?? new JObject(),
            error = null,
            warnings = new System.Collections.Generic.List<ProtocolWarning>(),
        };
        RecordTrace("outgoing", envelope);
        return JsonConvert.SerializeObject(envelope);
    }

    /// <summary>
    /// 消费协议控制消息；旧扁平消息返回 false 交给现有路由。
    /// </summary>
    public bool TryConsumeControlMessage(string json)
    {
        var root = JObject.Parse(json);
        if (root["protocol_version"] == null)
            return false;

        var envelope = root.ToObject<ProtocolEnvelope>();
        if (envelope == null)
            throw new InvalidOperationException("协议 envelope 反序列化失败");
        if (envelope.protocol_version != SupportedVersion)
            throw new InvalidOperationException($"不支持协议版本: {envelope.protocol_version}");
        if (envelope.sequence != _lastReceivedSequence + 1)
            throw new InvalidOperationException($"协议 sequence 不连续: expected={_lastReceivedSequence + 1}, actual={envelope.sequence}");

        _lastReceivedSequence = envelope.sequence;
        RecordTrace("incoming", envelope);
        if (envelope.error != null)
            LastProtocolError = envelope.error.code;

        if (envelope.type == "hello_ack")
        {
            SessionId = envelope.session_id;
            IsNegotiated = true;
            EnvelopeReceived?.Invoke(envelope);
            return true;
        }
        if (envelope.type == "protocol_error")
            return true;
        EnvelopeReceived?.Invoke(envelope);
        return true;
    }

    /// <summary>
    /// 返回协议轨迹副本，可按 request_id 过滤并限制最近条数。
    /// </summary>
    public List<ProtocolTraceEntry> GetTraceSnapshot(string requestId = null, int limit = 50)
    {
        var matches = new List<ProtocolTraceEntry>();
        foreach (ProtocolTraceEntry entry in _trace)
        {
            if (string.IsNullOrWhiteSpace(requestId) || entry.request_id == requestId)
                matches.Add(entry);
        }

        int resolvedLimit = Math.Max(1, Math.Min(limit, TraceCapacity));
        if (matches.Count <= resolvedLimit)
            return matches;
        return matches.GetRange(matches.Count - resolvedLimit, resolvedLimit);
    }

    /// <summary>
    /// 记录固定容量的 envelope 元数据，不保存完整 payload。
    /// </summary>
    private void RecordTrace(string direction, ProtocolEnvelope envelope)
    {
        if (_trace.Count >= TraceCapacity)
            _trace.Dequeue();
        _trace.Enqueue(new ProtocolTraceEntry
        {
            direction = direction,
            type = envelope.type ?? string.Empty,
            request_id = envelope.request_id ?? string.Empty,
            session_id = envelope.session_id ?? string.Empty,
            sequence = envelope.sequence,
            sent_at = envelope.sent_at ?? string.Empty,
            observed_at = DateTime.UtcNow.ToString("O"),
            error_code = envelope.error?.code ?? string.Empty,
        });
    }
}
