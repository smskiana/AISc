using System;
using MCPForUnity.Editor.Helpers;
using MCPForUnity.Editor.Tools;
using Newtonsoft.Json.Linq;

/// <summary>
/// 将 AISc 运行时业务诊断能力暴露为单一项目专用 Unity MCP 工具。
/// </summary>
[McpForUnityTool("aisc_debug", Description = "Read-only AISc runtime diagnostics: runtime_snapshot, health_report, protocol_trace, npc_task_snapshot, npc_social_snapshot, npc_runtime_state_snapshot, daily_schedule_snapshot, conversation_retrieval_snapshot, memory_retrieval_snapshot, midnight_snapshot, player_reply_suggestion_snapshot, initial_knowledge_projection_snapshot.")]
public static class AiscDebugMcpTool
{
    /// <summary>
    /// 声明 MCP schema 使用的只读诊断参数。
    /// </summary>
    public sealed class Parameters
    {
        [ToolParameter("Diagnostic action name.")]
        public string action { get; set; }

        [ToolParameter("Optional protocol request id filter.", Required = false)]
        public string request_id { get; set; }

        [ToolParameter("Optional NPC id filter.", Required = false)]
        public string npc_id { get; set; }

        [ToolParameter("Optional conversation id filter.", Required = false)]
        public string conversation_id { get; set; }

        [ToolParameter("Optional speaker id filter.", Required = false)]
        public string speaker_id { get; set; }

        [ToolParameter("Optional retrieval strategy filter.", Required = false)]
        public string strategy { get; set; }

        [ToolParameter("Optional retrieval trace id filter.", Required = false)]
        public string retrieval_trace_id { get; set; }

        [ToolParameter("Optional player reply suggestion trace id filter.", Required = false)]
        public string reply_trace_id { get; set; }

        [ToolParameter("Optional retrieval mode filter.", Required = false)]
        public string mode { get; set; }

        [ToolParameter("Optional initial knowledge source fact id filter.", Required = false)]
        public string source_fact_id { get; set; }

        [ToolParameter("Include facts excluded by observer permissions.", Required = false, DefaultValue = "false")]
        public bool include_excluded { get; set; }

        [ToolParameter("Optional result limit.", Required = false, DefaultValue = "50")]
        public int limit { get; set; }
    }

    /// <summary>
    /// 校验 action 参数并返回结构化诊断结果。
    /// </summary>
    public static object HandleCommand(JObject parameters)
    {
        try
        {
            var toolParams = new ToolParams(parameters ?? new JObject());
            string action = toolParams.Get("action", string.Empty).Trim().ToLowerInvariant();
            switch (action)
            {
                case "runtime_snapshot":
                    return new SuccessResponse("AISc runtime snapshot collected.", AiscDiagnostics.GetRuntimeSnapshot());
                case "health_report":
                    return new SuccessResponse("AISc health report collected.", AiscDiagnostics.GetHealthReport());
                case "protocol_trace":
                    return new SuccessResponse(
                        "AISc protocol trace collected.",
                        AiscDiagnostics.GetProtocolTrace(
                            toolParams.Get("request_id"),
                            Math.Max(1, Math.Min(toolParams.GetInt("limit") ?? 50, 200))));
                case "npc_task_snapshot":
                    return new SuccessResponse(
                        "AISc NPC task snapshot collected.",
                        AiscDiagnostics.GetNpcTaskSnapshots(toolParams.Get("npc_id")));
                case "npc_social_snapshot":
                    return new SuccessResponse(
                        "AISc NPC social snapshot collected.",
                        AiscDiagnostics.GetNpcSocialSnapshots(toolParams.Get("npc_id")));
                case "npc_runtime_state_snapshot":
                    return new SuccessResponse(
                        "AISc NPC runtime state snapshot collected.",
                        AiscDiagnostics.GetNpcRuntimeStateSnapshots(toolParams.Get("npc_id")));
                case "daily_schedule_snapshot":
                    return new SuccessResponse(
                        "AISc daily schedule snapshot collected.",
                        AiscDiagnostics.GetDailyScheduleSnapshots(toolParams.Get("npc_id")));
                case "conversation_retrieval_snapshot":
                    return new SuccessResponse(
                        "AISc conversation retrieval snapshot collected.",
                        AiscDiagnostics.GetConversationRetrievalSnapshots(
                            toolParams.Get("conversation_id"),
                            toolParams.Get("speaker_id")));
                case "memory_retrieval_snapshot":
                    return new SuccessResponse(
                        "AISc memory retrieval snapshot collected.",
                        AiscDiagnostics.GetMemoryRetrievalSnapshots(
                            toolParams.Get("retrieval_trace_id"),
                            toolParams.Get("npc_id"),
                            toolParams.Get("mode"),
                            toolParams.Get("strategy"),
                            Math.Max(1, Math.Min(toolParams.GetInt("limit") ?? 50, 100))));
                case "midnight_snapshot":
                    return new SuccessResponse(
                        "AISc midnight maintenance snapshot collected.",
                        AiscDiagnostics.GetMidnightMaintenanceSnapshot());
                case "player_reply_suggestion_snapshot":
                    return new SuccessResponse(
                        "AISc player reply suggestion snapshot collected.",
                        AiscDiagnostics.GetPlayerReplySuggestionSnapshots(
                            toolParams.Get("reply_trace_id"),
                            toolParams.Get("npc_id"),
                            Math.Max(1, Math.Min(toolParams.GetInt("limit") ?? 50, 100))));
                case "initial_knowledge_projection_snapshot":
                    return new SuccessResponse(
                        "AISc initial knowledge projection snapshot collected.",
                        AiscDiagnostics.GetInitialKnowledgeProjectionSnapshot(
                            toolParams.Get("npc_id"),
                            toolParams.Get("source_fact_id"),
                            string.Equals(toolParams.Get("include_excluded", "false"), "true", StringComparison.OrdinalIgnoreCase)));
                default:
                    return new ErrorResponse(
                        "Unknown action. Valid actions: runtime_snapshot, health_report, protocol_trace, npc_task_snapshot, npc_social_snapshot, npc_runtime_state_snapshot, daily_schedule_snapshot, conversation_retrieval_snapshot, memory_retrieval_snapshot, midnight_snapshot, player_reply_suggestion_snapshot, initial_knowledge_projection_snapshot.");
            }
        }
        catch (Exception error)
        {
            return new ErrorResponse($"AISc diagnostics failed: {error.Message}");
        }
    }
}
