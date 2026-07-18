using System;
using System.Collections.Generic;
using System.Net;
using UnityEngine;
using UnityEngine.SceneManagement;
using Newtonsoft.Json;

/// <summary>
/// 为编辑器工具和自动测试提供稳定的 Unity 业务诊断 seam。
/// </summary>
public static class AiscDiagnostics
{
    /// <summary>
    /// 收集当前运行状态，不修改任何游戏对象或业务状态。
    /// </summary>
    public static RuntimeDiagnosticSnapshot GetRuntimeSnapshot()
    {
        var snapshot = new RuntimeDiagnosticSnapshot
        {
            is_playing = Application.isPlaying,
            scene = SceneManager.GetActiveScene().name ?? string.Empty,
        };

        if (!Application.isPlaying)
            return snapshot;

        GameManager gameManager = GameManager.Instance;
        snapshot.game_manager_present = gameManager != null;
        if (gameManager == null)
            return snapshot;

        snapshot.gameplay_ready = gameManager.IsGameplayReady;
        snapshot.is_sleeping = gameManager.IsSleeping;
        snapshot.is_dialogue_active = gameManager.IsDialogueActive;
        snapshot.dialogue_npc_id = gameManager.CurrentDialogueNpcId ?? string.Empty;
        snapshot.player_location_id = gameManager.PlayerLocation ?? string.Empty;
        snapshot.game_time = gameManager.CurrentTime;
        snapshot.npc_state_count = gameManager.NPCs?.Count ?? 0;
        snapshot.connection = CreateConnectionSnapshot(gameManager.WS);
        snapshot.save = CreateSaveSnapshot(gameManager.SaveService);
        snapshot.world_preparation = gameManager.WorldPreparationSnapshot;
        snapshot.pause = CreatePauseSnapshot();
        snapshot.active_conversations = gameManager.WS?.GetConversationDiagnostics()
            ?? new List<ConversationRetrievalDiagnosticSnapshot>();

        NpcSpawner spawner = UnityEngine.Object.FindObjectOfType<NpcSpawner>();
        if (spawner != null)
        {
            snapshot.npc_entity_count = Count(spawner.GetAllNpcIds());
            snapshot.npc_tasks = spawner.GetTaskDiagnosticSnapshots();
            snapshot.npc_runtime_states = spawner.GetRuntimeStateDiagnosticSnapshots();
        }

        return snapshot;
    }

    /// <summary>
    /// 根据运行快照生成总体健康状态和稳定问题码。
    /// </summary>
    public static DiagnosticHealthReport GetHealthReport()
    {
        RuntimeDiagnosticSnapshot snapshot = GetRuntimeSnapshot();
        var report = new DiagnosticHealthReport { snapshot = snapshot, status = "ready" };

        if (!snapshot.is_playing)
            AddIssue(report, "play_mode_required", "failed", "Unity 当前不在 Play Mode。");
        else if (!snapshot.game_manager_present)
            AddIssue(report, "game_manager_missing", "failed", "当前场景中没有可用的 GameManager。");
        else
        {
            if (snapshot.connection == null || !snapshot.connection.is_connected)
                AddIssue(report, "websocket_disconnected", "failed", snapshot.connection?.connection_error ?? "WebSocket 未连接。");
            else if (!snapshot.connection.protocol_negotiated)
                AddIssue(report, "protocol_not_negotiated", "degraded", "WebSocket 已连接，但协议握手尚未完成。");

            if (!snapshot.gameplay_ready)
                AddIssue(report, "gameplay_not_ready", "degraded", "游戏主循环尚未进入 ready 状态。");
            if (snapshot.npc_state_count > 0 && snapshot.npc_entity_count == 0)
                AddIssue(report, "npc_entities_missing", "degraded", "已有 NPC 状态，但场景中没有生成 NPC 实体。");
        }

        return report;
    }

    /// <summary>
    /// 返回最近协议轨迹，可按 request_id 过滤。
    /// </summary>
    public static List<ProtocolTraceEntry> GetProtocolTrace(string requestId = null, int limit = 50)
    {
        ProtocolClient protocol = GameManager.Instance?.WS?.Protocol;
        return protocol?.GetTraceSnapshot(requestId, limit) ?? new List<ProtocolTraceEntry>();
    }

    /// <summary>
    /// 返回全部或指定 NPC 的任务诊断快照。
    /// </summary>
    public static List<NpcTaskDiagnosticSnapshot> GetNpcTaskSnapshots(string npcId = null)
    {
        NpcSpawner spawner = UnityEngine.Object.FindObjectOfType<NpcSpawner>();
        if (spawner == null)
            return new List<NpcTaskDiagnosticSnapshot>();

        List<NpcTaskDiagnosticSnapshot> snapshots = spawner.GetTaskDiagnosticSnapshots();
        if (string.IsNullOrWhiteSpace(npcId))
            return snapshots;
        return snapshots.FindAll(item => item.npc_id == npcId);
    }

    /// <summary>
    /// 返回 Unity 权威社交 session 的 reservation、会合、内容、播放与终态阶段。
    /// </summary>
    public static List<NpcSocialDiagnosticSnapshot> GetNpcSocialSnapshots(string npcId = null)
    {
        List<NpcSocialDiagnosticSnapshot> snapshots = NpcSocialProtocolController.ActiveInstance?.GetDiagnosticSnapshots()
            ?? new List<NpcSocialDiagnosticSnapshot>();
        if (string.IsNullOrWhiteSpace(npcId))
            return snapshots;
        return snapshots.FindAll(item => item.npc_id == npcId || item.target_npc_id == npcId);
    }

    /// <summary>
    /// 返回 Unity 权威日程的 revision、pending 与最近切换裁决。
    /// </summary>
    public static List<NpcDailyScheduleDiagnosticSnapshot> GetDailyScheduleSnapshots(string npcId = null)
    {
        NpcSpawner spawner = UnityEngine.Object.FindObjectOfType<NpcSpawner>();
        List<NpcDailyScheduleDiagnosticSnapshot> snapshots = spawner?.GetDailyScheduleDiagnosticSnapshots()
            ?? new List<NpcDailyScheduleDiagnosticSnapshot>();
        if (string.IsNullOrWhiteSpace(npcId))
            return snapshots;
        return snapshots.FindAll(item => item.npc_id == npcId);
    }

    /// <summary>
    /// 返回 Unity 权威 NPC 运行时状态与最近 effect 应用结果。
    /// </summary>
    public static List<NpcRuntimeStateDiagnosticSnapshot> GetNpcRuntimeStateSnapshots(string npcId = null)
    {
        NpcSpawner spawner = UnityEngine.Object.FindObjectOfType<NpcSpawner>();
        List<NpcRuntimeStateDiagnosticSnapshot> snapshots = spawner?.GetRuntimeStateDiagnosticSnapshots()
            ?? new List<NpcRuntimeStateDiagnosticSnapshot>();
        if (string.IsNullOrWhiteSpace(npcId))
            return snapshots;
        return snapshots.FindAll(item => item.npc_id == npcId);
    }

    /// <summary>
    /// 返回全部或指定会话、说话者的逐轮实体和记忆检索诊断。
    /// </summary>
    public static List<ConversationRetrievalDiagnosticSnapshot> GetConversationRetrievalSnapshots(
        string conversationId = null,
        string speakerId = null)
    {
        return GameManager.Instance?.WS?.GetConversationDiagnostics(conversationId, speakerId)
            ?? new List<ConversationRetrievalDiagnosticSnapshot>();
    }

    /// <summary>
    /// 从后端读取最近的通用记忆检索 trace，不在 Unity 侧访问图和向量存储。
    /// </summary>
    public static List<MemoryRetrievalDiagnosticSnapshot> GetMemoryRetrievalSnapshots(
        string retrievalTraceId = null,
        string npcId = null,
        string mode = null,
        string strategy = null,
        int limit = 50)
    {
        if (!Application.isPlaying)
            return new List<MemoryRetrievalDiagnosticSnapshot>();

        WebSocketClient webSocket = GameManager.Instance?.WS;
        if (webSocket == null)
            return new List<MemoryRetrievalDiagnosticSnapshot>();

        try
        {
            Uri healthUri = new Uri(webSocket.HealthUrl);
            var endpoint = new UriBuilder(healthUri)
            {
                Path = "/api/memory/retrieval_snapshot",
                Query = BuildMemoryRetrievalQuery(retrievalTraceId, npcId, mode, strategy, limit),
            };
            using var client = new WebClient();
            string json = client.DownloadString(endpoint.Uri);
            return JsonConvert.DeserializeObject<MemoryRetrievalDiagnosticResponse>(json)?.items
                ?? new List<MemoryRetrievalDiagnosticSnapshot>();
        }
        catch (Exception error)
        {
            Debug.LogWarning($"[诊断] 通用记忆检索快照读取失败: {error.GetType().Name}");
            return new List<MemoryRetrievalDiagnosticSnapshot>();
        }
    }

    /// <summary>
    /// 从后端读取当前或最近一次午夜维护快照。
    /// </summary>
    public static MidnightMaintenanceDiagnosticSnapshot GetMidnightMaintenanceSnapshot()
    {
        var snapshot = new MidnightMaintenanceDiagnosticSnapshot { status = "unavailable", phase = "idle" };
        if (!Application.isPlaying)
        {
            snapshot.failure_reasons.Add("play_mode_required");
            return snapshot;
        }
        WebSocketClient webSocket = GameManager.Instance?.WS;
        if (webSocket == null)
        {
            snapshot.failure_reasons.Add("websocket_client_missing");
            return snapshot;
        }
        try
        {
            Uri healthUri = new Uri(webSocket.HealthUrl);
            var endpoint = new UriBuilder(healthUri) { Path = "/api/memory/midnight_snapshot" };
            using var client = new WebClient();
            return JsonConvert.DeserializeObject<MidnightMaintenanceDiagnosticSnapshot>(client.DownloadString(endpoint.Uri))
                ?? snapshot;
        }
        catch (Exception error)
        {
            snapshot.failure_reasons.Add($"backend_diagnostic_unavailable:{error.GetType().Name}");
            return snapshot;
        }
    }

    /// <summary>
    /// 从后端读取玩家快捷回复的安全摘要，不在 Unity 侧重建主体判断。
    /// </summary>
    public static List<PlayerReplySuggestionDiagnosticSnapshot> GetPlayerReplySuggestionSnapshots(
        string replyTraceId = null,
        string npcId = null,
        int limit = 50)
    {
        if (!Application.isPlaying)
            return new List<PlayerReplySuggestionDiagnosticSnapshot>();

        WebSocketClient webSocket = GameManager.Instance?.WS;
        if (webSocket == null)
            return new List<PlayerReplySuggestionDiagnosticSnapshot>();

        try
        {
            Uri healthUri = new Uri(webSocket.HealthUrl);
            var endpoint = new UriBuilder(healthUri)
            {
                Path = "/api/dialogue/player_reply_suggestion_snapshot",
                Query = BuildPlayerReplySuggestionQuery(replyTraceId, npcId, limit),
            };
            using var client = new WebClient();
            string json = client.DownloadString(endpoint.Uri);
            return JsonConvert.DeserializeObject<PlayerReplySuggestionDiagnosticResponse>(json)?.items
                ?? new List<PlayerReplySuggestionDiagnosticSnapshot>();
        }
        catch (Exception error)
        {
            Debug.LogWarning($"[诊断] 玩家快捷回复快照读取失败: {error.GetType().Name}");
            return new List<PlayerReplySuggestionDiagnosticSnapshot>();
        }
    }

    /// <summary>
    /// 通过后端正式检索 seam 执行只读探针，返回 trace id 供 aisc_debug 查询。
    /// </summary>
    public static MemoryRetrievalProbeResult RunMemoryRetrievalProbe(
        string npcId,
        string targetId,
        string queryText,
        string mode,
        string locationId,
        string gameTime)
    {
        var result = new MemoryRetrievalProbeResult { success = false, failure_reason = "play_mode_required" };
        if (!Application.isPlaying)
            return result;
        WebSocketClient webSocket = GameManager.Instance?.WS;
        if (webSocket == null)
        {
            result.failure_reason = "websocket_client_missing";
            return result;
        }
        try
        {
            Uri healthUri = new Uri(webSocket.HealthUrl);
            var endpoint = new UriBuilder(healthUri) { Path = "/api/memory/retrieval_probe" };
            using var client = new WebClient();
            client.Headers[HttpRequestHeader.ContentType] = "application/json";
            string body = JsonConvert.SerializeObject(new
            {
                npc_id = npcId ?? string.Empty,
                conversation_participant_ids = new[] { targetId ?? "player" },
                query_text = queryText ?? string.Empty,
                mode = mode ?? "player_dialogue",
                location_id = locationId ?? string.Empty,
                game_time = gameTime ?? string.Empty,
            });
            return JsonConvert.DeserializeObject<MemoryRetrievalProbeResult>(client.UploadString(endpoint.Uri, "POST", body))
                ?? new MemoryRetrievalProbeResult { failure_reason = "backend_diagnostic_empty_response" };
        }
        catch (Exception error)
        {
            return new MemoryRetrievalProbeResult { failure_reason = $"backend_diagnostic_unavailable:{error.GetType().Name}" };
        }
    }

    /// <summary>
    /// 从后端只读查询冷启动初始知识投影，不在 Unity 侧重建记忆图。
    /// </summary>
    public static InitialKnowledgeProjectionDiagnosticSnapshot GetInitialKnowledgeProjectionSnapshot(
        string npcId = null,
        string sourceFactId = null,
        bool includeExcluded = false)
    {
        var snapshot = new InitialKnowledgeProjectionDiagnosticSnapshot
        {
            npc_id = npcId ?? string.Empty,
            failure_reason = "",
        };
        if (!Application.isPlaying)
        {
            snapshot.failure_reason = "play_mode_required";
            return snapshot;
        }

        WebSocketClient webSocket = GameManager.Instance?.WS;
        if (webSocket == null)
        {
            snapshot.failure_reason = "websocket_client_missing";
            return snapshot;
        }

        try
        {
            Uri healthUri = new Uri(webSocket.HealthUrl);
            var endpoint = new UriBuilder(healthUri)
            {
                Path = $"/api/npc/{Uri.EscapeDataString(npcId ?? string.Empty)}/initial_knowledge_projection_snapshot",
                Query = BuildInitialKnowledgeQuery(sourceFactId, includeExcluded),
            };
            using var client = new WebClient();
            string json = client.DownloadString(endpoint.Uri);
            return JsonConvert.DeserializeObject<InitialKnowledgeProjectionDiagnosticSnapshot>(json)
                ?? new InitialKnowledgeProjectionDiagnosticSnapshot
                {
                    npc_id = npcId ?? string.Empty,
                    failure_reason = "backend_diagnostic_empty_response",
                };
        }
        catch (Exception error)
        {
            snapshot.failure_reason = $"backend_diagnostic_unavailable:{error.GetType().Name}";
            return snapshot;
        }
    }

    /// <summary>
    /// 将连接对象转换成稳定诊断 DTO。
    /// </summary>
    private static ConnectionDiagnosticSnapshot CreateConnectionSnapshot(WebSocketClient webSocket)
    {
        if (webSocket == null)
            return new ConnectionDiagnosticSnapshot { connection_error = "websocket_client_missing" };

        return new ConnectionDiagnosticSnapshot
        {
            is_connected = webSocket.IsConnected,
            is_connecting = webSocket.IsConnecting,
            connect_attempt_finished = webSocket.HasConnectAttemptFinished,
            connection_error = webSocket.LastConnectionError ?? string.Empty,
            protocol_negotiated = webSocket.Protocol.IsNegotiated,
            session_id = webSocket.Protocol.SessionId ?? string.Empty,
            protocol_error = webSocket.Protocol.LastProtocolError ?? string.Empty,
        };
    }

    /// <summary>
    /// 将存档服务转换成稳定诊断 DTO。
    /// </summary>
    private static SaveDiagnosticSnapshot CreateSaveSnapshot(UnitySaveService saveService)
    {
        return new SaveDiagnosticSnapshot
        {
            phase = saveService?.TransactionPhase.ToString() ?? "Unavailable",
            checkpoint_id = saveService?.ActiveCheckpointId ?? string.Empty,
            is_purging_for_new_game = saveService != null && saveService.IsPurgingForNewGame,
            last_new_game_purge_error = saveService?.LastNewGamePurgeError ?? string.Empty,
        };
    }

    /// <summary>
    /// 收集全局暂停控制器的当前状态。
    /// </summary>
    private static PauseDiagnosticSnapshot CreatePauseSnapshot()
    {
        PauseController pauseController = PauseController.Instance;
        return new PauseDiagnosticSnapshot
        {
            is_paused = pauseController != null && pauseController.IsPaused,
            active_sources = pauseController?.ActiveSources ?? Array.Empty<string>(),
            gameplay_paused = pauseController != null
                && pauseController.IsDomainPaused(PauseTimeDomain.Gameplay),
            ui_paused = pauseController != null
                && pauseController.IsDomainPaused(PauseTimeDomain.UI),
            fx_paused = pauseController != null
                && pauseController.IsDomainPaused(PauseTimeDomain.FX),
            gameplay_sources = pauseController?.CreateDomainSources(PauseTimeDomain.Gameplay)
                ?? Array.Empty<string>(),
            ui_sources = pauseController?.CreateDomainSources(PauseTimeDomain.UI)
                ?? Array.Empty<string>(),
            fx_sources = pauseController?.CreateDomainSources(PauseTimeDomain.FX)
                ?? Array.Empty<string>(),
            unity_time_scale = Time.timeScale,
            registered_fx_count = PauseFxAdapter.RegisteredFxCount,
            domain_paused_fx_count = PauseFxAdapter.DomainPausedFxCount,
        };
    }

    /// <summary>
    /// 构造初始知识诊断的只读查询参数。
    /// </summary>
    private static string BuildInitialKnowledgeQuery(string sourceFactId, bool includeExcluded)
    {
        string query = $"include_excluded={(includeExcluded ? "true" : "false")}";
        if (!string.IsNullOrWhiteSpace(sourceFactId))
            query = $"source_fact_id={Uri.EscapeDataString(sourceFactId)}&{query}";
        return query;
    }

    /// <summary>
    /// 构造通用记忆检索诊断的只读筛选参数。
    /// </summary>
    private static string BuildMemoryRetrievalQuery(string traceId, string npcId, string mode, string strategy, int limit)
    {
        var values = new List<string> { $"limit={Math.Max(1, Math.Min(limit, 100))}" };
        if (!string.IsNullOrWhiteSpace(traceId)) values.Add($"retrieval_trace_id={Uri.EscapeDataString(traceId)}");
        if (!string.IsNullOrWhiteSpace(npcId)) values.Add($"npc_id={Uri.EscapeDataString(npcId)}");
        if (!string.IsNullOrWhiteSpace(mode)) values.Add($"mode={Uri.EscapeDataString(mode)}");
        if (!string.IsNullOrWhiteSpace(strategy)) values.Add($"strategy={Uri.EscapeDataString(strategy)}");
        return string.Join("&", values);
    }

    /// <summary>
    /// 构造玩家快捷回复安全摘要的只读筛选参数。
    /// </summary>
    private static string BuildPlayerReplySuggestionQuery(string traceId, string npcId, int limit)
    {
        var values = new List<string> { $"limit={Math.Max(1, Math.Min(limit, 100))}" };
        if (!string.IsNullOrWhiteSpace(traceId)) values.Add($"reply_trace_id={Uri.EscapeDataString(traceId)}");
        if (!string.IsNullOrWhiteSpace(npcId)) values.Add($"npc_id={Uri.EscapeDataString(npcId)}");
        return string.Join("&", values);
    }

    /// <summary>
    /// 添加健康问题并提升总体严重度。
    /// </summary>
    private static void AddIssue(DiagnosticHealthReport report, string code, string severity, string message)
    {
        report.issues.Add(new DiagnosticIssue { code = code, severity = severity, message = message });
        if (severity == "failed" || report.status == "ready")
            report.status = severity;
    }

    /// <summary>
    /// 统计只读枚举数量，避免向诊断 DTO 暴露实时集合。
    /// </summary>
    private static int Count(IEnumerable<string> values)
    {
        int count = 0;
        if (values == null) return count;
        foreach (string _ in values) count++;
        return count;
    }
}
