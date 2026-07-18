using System;
using UnityEngine;

/// <summary>
/// 统一构造并发送 Unity 前端发往后端的游戏命令。
/// </summary>
public class GameCommandSender
{
    private readonly WebSocketClient _webSocketClient;

    public GameCommandSender(WebSocketClient webSocketClient)
    {
        _webSocketClient = webSocketClient;
    }

    /// <summary>
    /// 发送开局命令。
    /// </summary>
    public void SendGameStart(string mode, GameTime gameTime, long worldRevision)
    {
        Send(new GameStartCommand { mode = mode, game_time = gameTime, world_revision = worldRevision });
    }

    /// <summary>
    /// 发送玩家开始 NPC 对话命令。
    /// </summary>
    public void SendDialogueStart(string requestId, string npcId, string playerLocation, GameTime gameTime, long worldRevision, NpcVisualContext visualContext = null)
    {
        Send(new DialogueStartCommand
        {
            request_id = requestId,
            npc_id = npcId,
            player_location = playerLocation,
            game_time = gameTime,
            world_revision = worldRevision,
            visual_context = visualContext,
        });
    }

    /// <summary>
    /// 确认玩家与 NPC 的对话现场已经就绪，允许后端开始生成内容。
    /// </summary>
    public void SendDialogueReady(string requestId, string npcId, string playerLocation, NpcVisualContext visualContext)
    {
        Send(new DialogueReadyCommand
        {
            request_id = requestId,
            npc_id = npcId,
            player_location = playerLocation,
            visual_context = visualContext,
        });
    }

    /// <summary>
    /// 发送玩家结束 NPC 对话命令。
    /// </summary>
    public void SendDialogueEnd(string npcId, string reason)
    {
        SendDialogueEnd(npcId, reason, null, 0);
    }

    /// <summary>
    /// 发送玩家结束 NPC 对话命令，并携带 Unity 当前 world revision 供状态 effect 校验。
    /// </summary>
    public void SendDialogueEnd(string npcId, string reason, GameTime gameTime, long worldRevision)
    {
        Send(new DialogueEndCommand
        {
            npc_id = npcId,
            reason = reason,
            game_time = gameTime,
            world_revision = worldRevision,
        });
    }

    /// <summary>
    /// 发送玩家回复选项命令。
    /// </summary>
    public void SendPlayerChoice(string npcId, string choiceText)
    {
        Send(new PlayerChoiceCommand
        {
            npc_id = npcId,
            choice_text = choiceText ?? string.Empty,
        });
    }

    /// <summary>
    /// 请求 Python 对 Unity 当前游戏日执行完整午夜结算。
    /// </summary>
    public void SendMidnightSettlement(GameTime gameTime)
    {
        Send(new MidnightSettlementCommand { game_time = gameTime });
    }

    /// <summary>
    /// 发送玩家位置同步命令。
    /// </summary>
    public void SendPlayerMove(string locationId)
    {
        Send(new PlayerMoveCommand { location_id = locationId });
    }

    /// <summary>
    /// 非阻塞同步 Unity 已裁决的 NPC 运行时事实；后端不得以此启动或监督任务。
    /// </summary>
    public void SendNpcRuntimeEvent(
        string eventId,
        string requestId,
        string npcId,
        string actionId,
        string status,
        string actualLocationId,
        string reason)
    {
        Send(new NpcRuntimeEventCommand
        {
            event_id = eventId,
            request_id = requestId,
            npc_id = npcId,
            action_id = actionId,
            result = status,
            actual_location_id = actualLocationId,
            reason = reason,
        });
    }

    /// <summary>
    /// 请求 Python 为 Unity 已完成会合的社交 session 生成内容。
    /// </summary>
    public void SendNpcSocialContentRequest(string requestId, string candidateId, string npcId, string targetNpcId, string actualLocationId, GameTime gameTime, long worldRevision)
    {
        Send(new NpcSocialResultCommand
        {
            type = "NPC_SOCIAL_CONTENT_REQUEST",
            request_id = requestId,
            candidate_id = candidateId,
            npc_id = npcId,
            target_npc_id = targetNpcId,
            actual_location_id = actualLocationId,
            game_time = gameTime,
            world_revision = worldRevision,
        });
    }

    /// <summary>
    /// 回报 NPC-NPC 会合或气泡播放失败。
    /// </summary>
    public void SendNpcSocialFailed(string requestId, string npcId, string targetNpcId, string actualLocationId, string reason)
    {
        Send(new NpcSocialResultCommand
        {
            type = "NPC_SOCIAL_FAILED",
            request_id = requestId,
            npc_id = npcId,
            target_npc_id = targetNpcId,
            actual_location_id = actualLocationId,
            reason = reason,
        });
    }

    /// <summary>
    /// 回报关联气泡队列已经完整播放。
    /// </summary>
    public void SendNpcSocialComplete(string requestId, string npcId, string targetNpcId, string actualLocationId)
    {
        SendNpcSocialComplete(requestId, npcId, targetNpcId, actualLocationId, null, 0);
    }

    /// <summary>
    /// 回报关联气泡队列已完整播放，并携带当前 world revision。
    /// </summary>
    public void SendNpcSocialComplete(string requestId, string npcId, string targetNpcId, string actualLocationId, GameTime gameTime, long worldRevision)
    {
        Send(new NpcSocialResultCommand
        {
            type = "NPC_SOCIAL_COMPLETE",
            request_id = requestId,
            npc_id = npcId,
            target_npc_id = targetNpcId,
            actual_location_id = actualLocationId,
            game_time = gameTime,
            world_revision = worldRevision,
        });
    }

    /// <summary>
    /// 以 Unity 权威剩余日程请求后端重规划单名 NPC。
    /// </summary>
    public void SendNpcScheduleReplanRequest(
        string operationId,
        string npcId,
        string interactionType,
        string endReason,
        string interactionSummary,
        string[] participantIds,
        GameTime gameTime,
        long worldRevision,
        long baseScheduleRevision,
        System.Collections.Generic.List<NpcDailyScheduleItem> remainingSchedule,
        NpcState physicalState)
    {
        Send(new NpcScheduleReplanRequestCommand
        {
            operation_id = operationId,
            npc_id = npcId,
            interaction_type = interactionType,
            end_reason = endReason,
            interaction_summary = interactionSummary,
            participant_ids = participantIds,
            game_time = gameTime,
            world_revision = worldRevision,
            base_schedule_revision = baseScheduleRevision,
            remaining_schedule = remainingSchedule,
            physical_state = physicalState,
        });
    }

    /// <summary>
    /// 提交 Unity 物理筛出的社交候选，后端只返回意愿而不保留候选或冷却。
    /// </summary>
    public void SendNpcSocialDecisionRequest(string requestId, string candidateId, string npcId, string targetNpcId, string locationId, GameTime gameTime, long worldRevision)
    {
        Send(new NpcSocialDecisionRequestCommand
        {
            request_id = requestId,
            candidate_id = candidateId,
            npc_id = npcId,
            target_npc_id = targetNpcId,
            location_id = locationId,
            game_time = gameTime,
            world_revision = worldRevision,
        });
    }

    /// <summary>
    /// 发送存档请求。
    /// </summary>
    public void SendSave(string slot)
    {
        Debug.LogWarning("[GameCommandSender] 后端旧存档请求已移除，请使用 UnitySaveService。");
    }

    /// <summary>
    /// 发送读档请求。
    /// </summary>
    public void SendLoad(string slot)
    {
        Debug.LogWarning("[GameCommandSender] 后端旧读档请求已移除，请使用 UnitySaveService。");
    }

    /// <summary>
    /// 请求存档列表。
    /// </summary>
    public void RequestSavesList()
    {
        Debug.LogWarning("[GameCommandSender] 后端旧存档列表请求已移除，请使用 UnitySaveService。");
    }

    /// <summary>
    /// 序列化命令并交给 WebSocketClient 发送。
    /// </summary>
    private void Send<TCommand>(TCommand command)
    {
        if (_webSocketClient == null)
        {
            Debug.LogWarning("[GameCommandSender] WebSocketClient 未初始化，命令已丢弃");
            return;
        }

        _webSocketClient.Send(JsonUtility.ToJson(command));
    }

    [Serializable]
    private class GameStartCommand
    {
        public string type = "GAME_START";
        public string mode;
        public GameTime game_time;
        public long world_revision;
    }

    [Serializable]
    private class DialogueStartCommand
    {
        public string type = "DIALOGUE_START";
        public string request_id;
        public string npc_id;
        public string player_location;
        public GameTime game_time;
        public long world_revision;
        public NpcVisualContext visual_context;
    }

    [Serializable]
    private class DialogueReadyCommand
    {
        public string type = "DIALOGUE_READY";
        public string request_id;
        public string npc_id;
        public string player_location;
        public NpcVisualContext visual_context;
    }

    [Serializable]
    private class DialogueEndCommand
    {
        public string type = "DIALOGUE_END";
        public string npc_id;
        public string reason;
        public GameTime game_time;
        public long world_revision;
    }

    [Serializable]
    private class PlayerChoiceCommand
    {
        public string type = "PLAYER_CHOICE";
        public string npc_id;
        public string choice_text;
    }

    [Serializable]
    private class MidnightSettlementCommand
    {
        public string type = "MIDNIGHT_SETTLEMENT_REQUEST";
        public GameTime game_time;
    }

    [Serializable]
    private class PlayerMoveCommand
    {
        public string type = "PLAYER_MOVE";
        public string location_id;
    }

    [Serializable]
    private class NpcRuntimeEventCommand
    {
        public string type = "NPC_RUNTIME_EVENT";
        public string event_id;
        public string request_id;
        public string npc_id;
        public string action_id;
        public string result;
        public string actual_location_id;
        public string reason;
    }

    [Serializable]
    private class NpcSocialResultCommand
    {
        public string type;
        public string request_id;
        public string candidate_id;
        public string npc_id;
        public string target_npc_id;
        public string actual_location_id;
        public string reason;
        public GameTime game_time;
        public long world_revision;
    }

    [Serializable]
    private class NpcScheduleReplanRequestCommand
    {
        public string type = "NPC_SCHEDULE_REPLAN_REQUEST";
        public string operation_id;
        public string npc_id;
        public string interaction_type;
        public string end_reason;
        public string interaction_summary;
        public string[] participant_ids;
        public GameTime game_time;
        public long world_revision;
        public long base_schedule_revision;
        public System.Collections.Generic.List<NpcDailyScheduleItem> remaining_schedule;
        public NpcState physical_state;
    }

    [Serializable]
    private class NpcSocialDecisionRequestCommand
    {
        public string type = "NPC_SOCIAL_DECISION_REQUEST";
        public string request_id;
        public string candidate_id;
        public string npc_id;
        public string target_npc_id;
        public string location_id;
        public GameTime game_time;
        public long world_revision;
    }

}
