using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;

/// <summary>
/// Unity 与 Python 之间的版本化协议 envelope。
/// </summary>
[Serializable]
public class ProtocolEnvelope
{
    public int protocol_version;
    public string type;
    public string request_id;
    public string session_id;
    public long sequence;
    public string sent_at;
    public JObject payload;
    public ProtocolError error;
    public List<ProtocolWarning> warnings;
}

/// <summary>
/// 表示可供业务稳定判断的协议错误。
/// </summary>
[Serializable]
public class ProtocolError
{
    public string code;
    public string message;
    public bool retryable;
    public JObject details;
}

/// <summary>
/// 表示不阻断消息处理的协议警告。
/// </summary>
[Serializable]
public class ProtocolWarning
{
    public string code;
    public string message;
}
