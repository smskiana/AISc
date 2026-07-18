using System;
using System.Collections.Generic;

/// <summary>
/// WebSocket 消息类型定义 — 与 Python 后端一致。
/// </summary>
[Serializable]
public class GameTime
{
    public int day;
    public int hour;
    public int minute;
    public string weather;
}

[Serializable]
public class NpcState
{
    public string npc_id;
    public string emotion;
    public float energy;
    public float sociability;
    public string current_location;
    public string current_action;
    public int is_first_encounter;
    public string current_need;
}

[Serializable]
public class NpcBehaviorCmd
{
    public string action_id;
    public string location_id;
    public float duration_sec;
    public float expected_duration_sec;
    public string movement_mode;
    public bool interruptible;
}

[Serializable]
public class BehaviorContext
{
    public string reason;
    public string plan_source;
    public string mood_visible;
}

/// <summary>
/// 玩家搭话时附带的 NPC 当前前端视觉快照。
/// </summary>
[Serializable]
public class NpcVisualContext
{
    public string base_action_id;
    public string ambient_action_id;
    public string ambient_label;
    public string location_id;
    public bool is_interrupting_ambient;
}

[Serializable]
public class GameReadyMsg
{
    public string type;
    public string mode;
    public bool fresh_start;
    public GameTime game_time;
    public string weather;
    public string player_location;
    public List<NpcState> npcs;
}

[Serializable]
public class LoadCompleteMsg
{
    public string type;
    public GameTime game_time;
}

[Serializable]
public class NpcTaskCommand
{
    public string request_id;
    public string npc_id;
    public NpcBehaviorCmd behavior;
    public BehaviorContext context;
}

[Serializable]
public class DialoguePreparedMsg
{
    public string type;
    public string request_id;
    public string npc_id;
}

[Serializable]
public class DialogueTokenMsg
{
    public string type;
    public string npc_id;
    public string token;
    public bool is_complete;
}

[Serializable]
public class DialogueCompleteMsg
{
    public string type;
    public string npc_id;
    public string npc_text_complete;
    public string emotion_change;
    public List<string> choices;  // 玩家可选回复
}

[Serializable]
public class DialogueChoicesUpdateMsg
{
    public string type;
    public string npc_id;
    public List<string> choices;  // 后台生成完成后的玩家可选回复
}

[Serializable]
public class DialogueCloseMsg
{
    public string type;
    public string npc_id;
    public string reason;
}

[Serializable]
public class SaveCompleteMsg
{
    public string type;
    public bool success;
    public string slot;
}

[Serializable]
public class SavesListMsg
{
    public string type;
    public List<SaveInfo> saves;
}

[Serializable]
public class SaveInfo
{
    public string slot;
    public int game_day;
    public string saved_at;
    public string version;
    public string display_name;
    public bool is_auto;
    public string screenshot_path;
}

[Serializable]
public class GameErrorMsg
{
    public string type;
    public string request_id;
    public string message;
}

[Serializable]
public class MidnightSettlementCompleteMsg
{
    public string type;
    public string weather;
    public string operation_id;
    public string maintenance_status;
    public string[] failure_reasons;
}

[Serializable]
public class MidnightSettlementFailedMsg
{
    public string type;
    public string operation_id;
    public string reason;
}

/// <summary>
/// 表示后端世界准备阶段的体验反馈，不是精确真实进度。
/// </summary>
[Serializable]
public class WorldPreparationProgressMsg
{
    public string type;
    public string operation_id;
    public string flow;
    public string phase;
    public string message;
    public float progress_floor;
    public int target_game_day;
}

// ── NPC 对话气泡 ──
[Serializable]
public class NpcBubbleMsg
{
    public string type;          // "NPC_BUBBLE"
    public string request_id;
    public string npc_id;        // 说话方
    public string target_npc_id; // 目标方
    public string text;          // 气泡文字
    public float duration_sec;   // 显示时长
    public string style;         // "speech" | "thought" | "exclaim"
    public int line_index;
    public int line_count;
}

/// <summary>
/// 后端确认 NPC-NPC 社交终态是否被接受。
/// </summary>
[Serializable]
public class NpcSocialAckMsg
{
    public string type;
    public string request_id;
    public bool accepted;
    public string status;
    public string reason;
}

/// <summary>
/// Python 只返回语义意愿；Unity 必须重新校验物理条件后才会开始会合。
/// </summary>
[Serializable]
public class NpcSocialDecisionResultMsg
{
    public string type;
    public string request_id;
    public string candidate_id;
    public string npc_id;
    public string target_npc_id;
    public long world_revision;
    public bool want_to_talk;
    public string reason;
    public string opening_intent;
}

/// <summary>
/// Python 在 Unity 完成会合后返回的纯语义对白内容。
/// </summary>
[Serializable]
public class NpcSocialContentResultMsg
{
    public string type;
    public string request_id;
    public string candidate_id;
    public string npc_id;
    public string target_npc_id;
    public long world_revision;
    public bool success;
    public string reason;
    public List<NpcSocialContentLineMsg> lines = new();
}

[Serializable]
public class NpcSocialContentLineMsg
{
    public string speaker_npc_id;
    public string target_npc_id;
    public string text;
    public float duration_sec;
}

/// <summary>
/// Python 计算但由 Unity 校验应用的 NPC 运行时状态影响。
/// </summary>
[Serializable]
public class NpcStateEffectMsg
{
    public string type;
    public string operation_id;
    public string npc_id;
    public long base_world_revision;
    public string effect_type;
    public NpcStateEffectDeltas field_deltas;
    public NpcStateEffectValues field_values;
    public List<string> clamp_reasons = new List<string>();
    public string source;
    public string reason;
}

[Serializable]
public class NpcStateEffectDeltas
{
    public float energy;
    public float sociability;
}

[Serializable]
public class NpcStateEffectValues
{
    public string emotion;
    public float emotion_delta;
    public float sociability_delta;
    public string current_need;
    public string lingering_concern;
    public bool is_asleep;
}

/// <summary>
/// 后端给出互动摘要，Unity 以权威剩余计划回传每个受影响 NPC 的重规划请求。
/// </summary>
[Serializable]
public class NpcScheduleReplanContextMsg
{
    public string type;
    public string operation_id;
    public string interaction_id;
    public List<string> npc_ids = new List<string>();
    public List<string> participant_ids = new List<string>();
    public string interaction_type;
    public string end_reason;
    public string interaction_summary;
    public string location_id;
    public GameTime game_time;
    public List<NpcStateEffectMsg> state_effects = new List<NpcStateEffectMsg>();
    public long base_world_revision;
}

// ── NPC 社交动作 ──
[Serializable]
public class NpcSocialActionMsg
{
    public string type;           // "NPC_SOCIAL_ACTION"
    public string npc_id;         // 发起方
    public string target_npc_id;  // 目标方
    public string action_id;      // "talk" | "greet" | "give_item"
    public string item_id;        // 物品 ID（give_item 时用）
    public string location_id;    // 发生地点
}

/// <summary>
/// WS 消息分发 — type 字段路由到对应回调。
/// </summary>
public static class MessageRouter
{
    public static void Dispatch(string json, Callbacks cb)
    {
        var msg = UnityEngine.JsonUtility.FromJson<SimpleMsg>(json);
        switch (msg.type)
        {
            case "GAME_READY":
                cb.OnGameReady?.Invoke(UnityEngine.JsonUtility.FromJson<GameReadyMsg>(json));
                break;
            case "LOAD_COMPLETE":
                cb.OnLoadComplete?.Invoke(UnityEngine.JsonUtility.FromJson<LoadCompleteMsg>(json));
                break;
            case "NPC_DAILY_SCHEDULE_READY":
                cb.OnNpcDailyScheduleReady?.Invoke(UnityEngine.JsonUtility.FromJson<NpcDailyScheduleReadyMsg>(json));
                break;
            case "NPC_BUBBLE":
                cb.OnNpcBubble?.Invoke(UnityEngine.JsonUtility.FromJson<NpcBubbleMsg>(json));
                break;
            case "NPC_SOCIAL_ACTION":
                cb.OnNpcSocialAction?.Invoke(UnityEngine.JsonUtility.FromJson<NpcSocialActionMsg>(json));
                break;
            case "NPC_SOCIAL_ACK":
                cb.OnNpcSocialAck?.Invoke(UnityEngine.JsonUtility.FromJson<NpcSocialAckMsg>(json));
                break;
            case "NPC_SOCIAL_DECISION_RESULT":
                cb.OnNpcSocialDecisionResult?.Invoke(UnityEngine.JsonUtility.FromJson<NpcSocialDecisionResultMsg>(json));
                break;
            case "NPC_SOCIAL_CONTENT_RESULT":
                cb.OnNpcSocialContentResult?.Invoke(UnityEngine.JsonUtility.FromJson<NpcSocialContentResultMsg>(json));
                break;
            case "NPC_STATE_EFFECT":
                cb.OnNpcStateEffect?.Invoke(UnityEngine.JsonUtility.FromJson<NpcStateEffectMsg>(json));
                break;
            case "NPC_SCHEDULE_REPLAN_CONTEXT":
                cb.OnNpcScheduleReplanContext?.Invoke(UnityEngine.JsonUtility.FromJson<NpcScheduleReplanContextMsg>(json));
                break;
            case "DIALOGUE_TOKEN":
                cb.OnDialogueToken?.Invoke(UnityEngine.JsonUtility.FromJson<DialogueTokenMsg>(json));
                break;
            case "DIALOGUE_PREPARED":
                cb.OnDialoguePrepared?.Invoke(UnityEngine.JsonUtility.FromJson<DialoguePreparedMsg>(json));
                break;
            case "DIALOGUE_COMPLETE":
                cb.OnDialogueComplete?.Invoke(UnityEngine.JsonUtility.FromJson<DialogueCompleteMsg>(json));
                break;
            case "DIALOGUE_CHOICES_UPDATE":
                cb.OnDialogueChoicesUpdate?.Invoke(UnityEngine.JsonUtility.FromJson<DialogueChoicesUpdateMsg>(json));
                break;
            case "DIALOGUE_CLOSE":
                cb.OnDialogueClose?.Invoke(UnityEngine.JsonUtility.FromJson<DialogueCloseMsg>(json));
                break;
            case "SAVE_COMPLETE":
                cb.OnSaveComplete?.Invoke(UnityEngine.JsonUtility.FromJson<SaveCompleteMsg>(json));
                break;
            case "SAVES_LIST":
                cb.OnSavesList?.Invoke(UnityEngine.JsonUtility.FromJson<SavesListMsg>(json));
                break;
            case "GAME_ERROR":
                cb.OnGameError?.Invoke(UnityEngine.JsonUtility.FromJson<GameErrorMsg>(json));
                break;
            case "MIDNIGHT_SETTLEMENT_COMPLETE":
                cb.OnMidnightSettlementComplete?.Invoke(UnityEngine.JsonUtility.FromJson<MidnightSettlementCompleteMsg>(json));
                break;
            case "MIDNIGHT_SETTLEMENT_FAILED":
                cb.OnMidnightSettlementFailed?.Invoke(UnityEngine.JsonUtility.FromJson<MidnightSettlementFailedMsg>(json));
                break;
            case "WORLD_PREPARATION_PROGRESS":
                cb.OnWorldPreparationProgress?.Invoke(UnityEngine.JsonUtility.FromJson<WorldPreparationProgressMsg>(json));
                break;
        }
    }
}

[Serializable]
public class SimpleMsg { public string type; }

public class Callbacks
{
    public Action<GameReadyMsg> OnGameReady;
    public Action<LoadCompleteMsg> OnLoadComplete;
    public Action<NpcDailyScheduleReadyMsg> OnNpcDailyScheduleReady;
    public Action<DialoguePreparedMsg> OnDialoguePrepared;
    public Action<DialogueTokenMsg> OnDialogueToken;
    public Action<DialogueCompleteMsg> OnDialogueComplete;
    public Action<DialogueChoicesUpdateMsg> OnDialogueChoicesUpdate;
    public Action<DialogueCloseMsg> OnDialogueClose;
    public Action<SaveCompleteMsg> OnSaveComplete;
    public Action<SavesListMsg> OnSavesList;
    public Action<GameErrorMsg> OnGameError;
    public Action<NpcBubbleMsg> OnNpcBubble;
    public Action<NpcSocialActionMsg> OnNpcSocialAction;
    public Action<NpcSocialAckMsg> OnNpcSocialAck;
    public Action<NpcSocialDecisionResultMsg> OnNpcSocialDecisionResult;
    public Action<NpcSocialContentResultMsg> OnNpcSocialContentResult;
    public Action<NpcStateEffectMsg> OnNpcStateEffect;
    public Action<NpcScheduleReplanContextMsg> OnNpcScheduleReplanContext;
    public Action<MidnightSettlementCompleteMsg> OnMidnightSettlementComplete;
    public Action<MidnightSettlementFailedMsg> OnMidnightSettlementFailed;
    public Action<WorldPreparationProgressMsg> OnWorldPreparationProgress;
}
