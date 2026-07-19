#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using MCPForUnity.Editor.Helpers;
using MCPForUnity.Editor.Tools;
using Newtonsoft.Json.Linq;
using UnityEngine;

/// <summary>
/// 暴露仅编辑器可用的 AISc 白名单运行态控制能力。
/// </summary>
[McpForUnityTool("aisc_control", Description = "Editor-only AISc runtime controls including isolated daily schedule probes.")]
public static class AiscControlMcpTool
{
    private static readonly Dictionary<string, Func<ToolParams, object>> ActionHandlers = new()
    {
        ["start_new_game"] = _ => StartNewGame(),
        ["start_dialogue"] = StartDialogue,
        ["send_player_choice"] = SendPlayerChoice,
        ["end_dialogue"] = EndDialogue,
        ["run_midnight_settlement"] = _ => RunMidnightSettlement(),
        ["request_pause_test"] = _ => SetPauseTest(true),
        ["release_pause_test"] = _ => SetPauseTest(false),
        ["run_memory_retrieval_probe"] = RunMemoryRetrievalProbe,
        ["run_daily_schedule_probe"] = RunDailyScheduleProbe,
        ["run_npc_social_probe"] = RunNpcSocialProbe,
        ["start_npc_social_playmode_probe"] = StartNpcSocialPlayModeProbe,
    };

    /// <summary>
    /// 声明 MCP schema 使用的白名单控制参数。
    /// </summary>
    public sealed class Parameters
    {
        [ToolParameter("Control action name.")]
        public string action { get; set; }

        [ToolParameter("Optional NPC id.", Required = false)]
        public string npc_id { get; set; }

        [ToolParameter("Optional target participant id for retrieval probe.", Required = false)]
        public string target_id { get; set; }

        [ToolParameter("Optional location id.", Required = false)]
        public string location_id { get; set; }

        [ToolParameter("Optional player choice text.", Required = false)]
        public string choice_text { get; set; }

        [ToolParameter("Optional retrieval query.", Required = false)]
        public string query_text { get; set; }

        [ToolParameter("Optional retrieval mode.", Required = false)]
        public string mode { get; set; }

        [ToolParameter("Whitelisted probe scenario for schedule or NPC social probes.", Required = false)]
        public string scenario { get; set; }
    }

    /// <summary>
    /// 校验 action 并调用明确允许的编辑器运行态入口。
    /// </summary>
    public static object HandleCommand(JObject parameters)
    {
        try
        {
            var toolParams = new ToolParams(parameters ?? new JObject());
            string action = toolParams.Get("action", string.Empty).Trim().ToLowerInvariant();
            if (ActionHandlers.TryGetValue(action, out var handler))
                return handler(toolParams);
            return new ErrorResponse("Unknown action. Valid actions: start_new_game, start_dialogue, send_player_choice, end_dialogue, run_midnight_settlement, request_pause_test, release_pause_test, run_memory_retrieval_probe, run_daily_schedule_probe, run_npc_social_probe, start_npc_social_playmode_probe.");
        }
        catch (Exception error)
        {
            return new ErrorResponse($"AISc editor control failed: {error.Message}");
        }
    }

    /// <summary>
    /// 通过开始菜单控制器进入无存档新游戏流程。
    /// </summary>
    private static object StartNewGame()
    {
        if (!Application.isPlaying)
            return new ErrorResponse("Unity must be in Play Mode.");

        StartMenuController controller = UnityEngine.Object.FindObjectOfType<StartMenuController>();
        if (controller == null)
            return new ErrorResponse("StartMenuController is unavailable.");
        if (!controller.StartNewGameForEditorDiagnostics())
            return new ErrorResponse("Backend connection is not ready.");

        return new SuccessResponse("AISc new game requested.", new { action = "start_new_game" });
    }

    /// <summary>
    /// 通过 GameManager 正式入口开始玩家对话。
    /// </summary>
    private static object StartDialogue(ToolParams parameters)
    {
        if (!Application.isPlaying)
            return new ErrorResponse("Unity must be in Play Mode.");
        GameManager manager = GameManager.Instance;
        string npcId = parameters.Get("npc_id", string.Empty);
        if (manager == null || !manager.IsGameplayReady || string.IsNullOrWhiteSpace(npcId))
            return new ErrorResponse("Gameplay or npc_id is unavailable.");
        manager.StartDialogue(npcId, parameters.Get("location_id", manager.PlayerLocation ?? "player_cafe.doorway"));
        return new SuccessResponse("AISc dialogue start requested.", new { action = "start_dialogue", npc_id = npcId });
    }

    /// <summary>
    /// 通过 GameManager 正式入口发送玩家选择。
    /// </summary>
    private static object SendPlayerChoice(ToolParams parameters)
    {
        if (!Application.isPlaying)
            return new ErrorResponse("Unity must be in Play Mode.");
        GameManager manager = GameManager.Instance;
        string npcId = parameters.Get("npc_id", manager?.CurrentDialogueNpcId ?? string.Empty);
        string choice = parameters.Get("choice_text", string.Empty);
        if (manager == null || !manager.IsDialogueActive || string.IsNullOrWhiteSpace(npcId) || string.IsNullOrWhiteSpace(choice))
            return new ErrorResponse("Active dialogue, npc_id and choice_text are required.");
        manager.SendPlayerChoice(npcId, choice);
        return new SuccessResponse("AISc player choice sent.", new { action = "send_player_choice", npc_id = npcId });
    }

    /// <summary>
    /// 通过 GameManager 正式入口结束玩家对话。
    /// </summary>
    private static object EndDialogue(ToolParams parameters)
    {
        if (!Application.isPlaying || GameManager.Instance == null)
            return new ErrorResponse("Unity must be in Play Mode with GameManager.");
        GameManager.Instance.EndDialogue("editor_diagnostics");
        return new SuccessResponse("AISc dialogue end requested.", new { action = "end_dialogue" });
    }

    /// <summary>
    /// 通过正式睡眠控制器触发午夜结算；完成状态由 aisc_debug.midnight_snapshot 等待验证。
    /// </summary>
    private static object RunMidnightSettlement()
    {
        if (!Application.isPlaying)
            return new ErrorResponse("Unity must be in Play Mode.");
        SleepController controller = UnityEngine.Object.FindObjectOfType<SleepController>();
        if (controller == null || !controller.StartMidnightForEditorDiagnostics())
            return new ErrorResponse("SleepController is unavailable or settlement is already running.");
        return new SuccessResponse("AISc midnight settlement requested.", new { action = "run_midnight_settlement" });
    }

    /// <summary>
    /// 通过固定诊断来源申请或释放世界暂停，不接受任意来源和时间域参数。
    /// </summary>
    private static object SetPauseTest(bool paused)
    {
        if (!Application.isPlaying || PauseController.Instance == null)
            return new ErrorResponse("Unity must be in Play Mode with PauseController.");

        if (paused)
            PauseController.Instance.RequestPause(PauseSources.DiagnosticsTest);
        else
            PauseController.Instance.ReleasePause(PauseSources.DiagnosticsTest);

        return new SuccessResponse(
            paused ? "AISc pause test requested." : "AISc pause test released.",
            new { action = paused ? "request_pause_test" : "release_pause_test" });
    }

    /// <summary>
    /// 执行当前 YAML mode policy 的只读检索探针，不允许策略覆盖。
    /// </summary>
    private static object RunMemoryRetrievalProbe(ToolParams parameters)
    {
        if (!Application.isPlaying)
            return new ErrorResponse("Unity must be in Play Mode.");
        GameManager manager = GameManager.Instance;
        string npcId = parameters.Get("npc_id", manager?.CurrentDialogueNpcId ?? string.Empty);
        string targetId = parameters.Get("target_id", "player");
        string mode = parameters.Get("mode", "player_dialogue");
        string query = parameters.Get("query_text", string.Empty);
        var result = AiscDiagnostics.RunMemoryRetrievalProbe(
            npcId,
            targetId,
            query,
            mode,
            parameters.Get("location_id", manager?.PlayerLocation ?? string.Empty),
            manager?.CurrentTime.ToString() ?? string.Empty);
        return result.success
            ? new SuccessResponse("AISc memory retrieval probe completed.", result)
            : new ErrorResponse($"AISc memory retrieval probe failed: {result.failure_reason}");
    }

    /// <summary>
    /// 调用正式日程控制器 seam 执行白名单隔离探针，写入范围仅为临时内存对象。
    /// </summary>
    private static object RunDailyScheduleProbe(ToolParams parameters)
    {
        string scenario = parameters.Get("scenario", string.Empty);
        DailyScheduleProbeResult result = scenario == "fixed_input_planner" || scenario == "provider_timeout"
            ? AiscDiagnostics.RunBackendDailyScheduleProbe(scenario)
            : AiscDiagnostics.RunDailyScheduleProbe(scenario);
        return result.success
            ? new SuccessResponse("AISc isolated daily schedule probe completed.", result)
            : new ErrorResponse($"AISc daily schedule probe failed: {result.failure_reason}");
    }

    /// <summary>
    /// 调用正式社交协议状态转移执行白名单隔离探针。
    /// </summary>
    private static object RunNpcSocialProbe(ToolParams parameters)
    {
        NpcSocialProbeResult result = AiscDiagnostics.RunNpcSocialProbe(parameters.Get("scenario", string.Empty));
        return result.success
            ? new SuccessResponse("AISc isolated NPC social probe completed.", result)
            : new ErrorResponse($"AISc NPC social probe failed: {result.failure_reason}");
    }

    /// <summary>
    /// 使用固定 NPC 与地点启动真实移动、抢占或移动取消社交长链。
    /// </summary>
    private static object StartNpcSocialPlayModeProbe(ToolParams parameters)
    {
        if (!Application.isPlaying || GameManager.Instance == null || !GameManager.Instance.IsGameplayReady)
            return new ErrorResponse("Unity must be in ready Play Mode.");

        string scenario = parameters.Get("scenario", string.Empty).Trim().ToLowerInvariant();
        if (scenario != "cross_location_complete" && scenario != "player_preempt" && scenario != "rendezvous_failure")
            return new ErrorResponse("Unknown NPC social PlayMode scenario.");

        NpcSpawner spawner = UnityEngine.Object.FindObjectOfType<NpcSpawner>();
        NpcEntity npcA = spawner?.GetNpc("sakura");
        NpcEntity npcB = spawner?.GetNpc("chihaya");
        NpcSocialProtocolController protocol = NpcSocialProtocolController.ActiveInstance;
        if (npcA == null || npcB == null || protocol == null)
            return new ErrorResponse("Fixed NPC social probe participants are unavailable.");
        if (NpcSocialProtocolController.IsNpcReserved(npcA.NpcId)
            || NpcSocialProtocolController.IsNpcReserved(npcB.NpcId))
            return new ErrorResponse("Fixed NPC social probe participants are already reserved.");

        npcA.TeleportTo("street.arcade");
        npcB.TeleportTo("street.vending_machine");
        string requestId = $"social_playmode_probe_{scenario}_{Guid.NewGuid():N}";
        bool started = protocol.Begin(new NpcSocialDecisionResultMsg
        {
            request_id = requestId,
            candidate_id = requestId,
            npc_id = npcA.NpcId,
            target_npc_id = npcB.NpcId,
            world_revision = GameManager.Instance.WorldRevision,
            want_to_talk = true,
        }, "street.crossroad");
        if (!started)
            return new ErrorResponse("NPC social PlayMode probe was rejected by the protocol controller.");

        if (scenario == "player_preempt")
            GameManager.Instance.StartDialogue(npcA.NpcId, "street.crossroad");
        else if (scenario == "rendezvous_failure")
            npcA.MoveToLocation("street.bulletin_board");

        return new SuccessResponse("AISc NPC social PlayMode probe started.", new
        {
            action = "start_npc_social_playmode_probe",
            scenario,
            request_id = requestId,
            npc_id = npcA.NpcId,
            target_npc_id = npcB.NpcId,
            start_location_a = "street.arcade",
            start_location_b = "street.vending_machine",
            rendezvous_location = "street.crossroad",
            write_scope = "current_play_session_only",
        });
    }
}
#endif
