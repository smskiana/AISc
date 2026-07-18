using System.Collections.Generic;

/// <summary>
/// 保存 Unity 前端当前游戏状态，并提供集中写入入口。
/// </summary>
public class GameStateStore
{
    private long _worldRevision;
    public List<NpcState> NPCs { get; private set; } = new List<NpcState>();
    public string PlayerLocation { get; private set; } = "player_cafe.doorway";
    public bool IsSleeping { get; private set; }
    public bool IsDialogueActive { get; private set; }
    public bool IsGameplayReady { get; private set; }
    public string CurrentDialogueNpcId { get; private set; }
    public long WorldRevision => _worldRevision;
    private System.Action<List<NpcWorldSaveData>> _writeDailySchedules;
    private System.Action<GameSaveData> _restoreDailySchedules;

    /// <summary>
    /// 由场景中的日程托管器注册存读档桥接，避免状态仓库持有场景对象。
    /// </summary>
    public void SetDailySchedulePersistence(
        System.Action<List<NpcWorldSaveData>> writeDailySchedules,
        System.Action<GameSaveData> restoreDailySchedules)
    {
        _writeDailySchedules = writeDailySchedules;
        _restoreDailySchedules = restoreDailySchedules;
    }

    /// <summary>
    /// 标记游戏主循环暂不可交互。
    /// </summary>
    public void MarkGameplayNotReady()
    {
        IsGameplayReady = false;
    }

    /// <summary>
    /// 标记世界准备成功完成，允许主循环重新接收交互输入。
    /// </summary>
    public void MarkGameplayReady()
    {
        IsGameplayReady = true;
    }

    /// <summary>
    /// 应用 GAME_READY 消息中的全量游戏状态。
    /// </summary>
    public void ApplyGameReady(GameReadyMsg msg)
    {
        IsGameplayReady = true;
        PlayerLocation = msg.player_location;
        NPCs = msg.npcs ?? new List<NpcState>();
        _worldRevision++;
    }

    /// <summary>
    /// 应用 LOAD_COMPLETE 消息中的时间状态。
    /// </summary>
    public void ApplyLoadComplete(LoadCompleteMsg msg)
    {
    }

    /// <summary>
    /// 更新睡眠状态。
    /// </summary>
    public void SetSleeping(bool isSleeping)
    {
        IsSleeping = isSleeping;
    }

    /// <summary>
    /// 应用 Unity 内部任务意图；位置必须等待场景执行成功后再确认。
    /// </summary>
    public void ApplyNpcBehavior(NpcTaskCommand msg)
    {
        var npc = FindNpc(msg.npc_id);
        if (npc == null || msg.behavior == null)
            return;

        npc.current_action = msg.behavior.action_id;
    }

    /// <summary>
    /// 行为成功后把 Unity 场景确认的实际位置写入本地状态缓存。
    /// </summary>
    public void ApplyNpcActionResult(string npcId, string status, string actualLocationId)
    {
        if (status != "succeeded" || string.IsNullOrWhiteSpace(actualLocationId))
            return;

        var npc = FindNpc(npcId);
        if (npc != null)
            npc.current_location = actualLocationId;
    }

    /// <summary>
    /// 设置玩家当前位置。
    /// </summary>
    public void SetPlayerLocation(string locationId)
    {
        PlayerLocation = locationId;
        _worldRevision++;
    }

    /// <summary>
    /// 导出只包含稳定世界事实的 Unity 主存档快照。
    /// </summary>
    public GameSaveData CreateSaveData(
        string slotId,
        string saveId,
        string checkpointId,
        GameTime gameTime,
        List<InventoryEntrySaveData> inventory)
    {
        var data = new GameSaveData
        {
            save_id = saveId,
            slot_id = slotId,
            checkpoint_id = checkpointId,
            created_at = System.DateTime.UtcNow.ToString("O"),
            world_revision = _worldRevision,
            game_time = gameTime,
            weather = gameTime?.weather,
            player = new PlayerSaveData
            {
                location_id = PlayerLocation,
                inventory = inventory ?? new List<InventoryEntrySaveData>(),
            },
        };
        foreach (var npc in NPCs)
        {
            data.npcs.Add(new NpcWorldSaveData
            {
                npc_id = npc.npc_id,
                location_id = npc.current_location,
                emotion = npc.emotion,
                energy = npc.energy,
                sociability = npc.sociability,
                is_asleep = false,
                current_need = npc.current_need,
            });
        }
        _writeDailySchedules?.Invoke(data.npcs);
        return data;
    }

    /// <summary>
    /// 用 Unity 主存档覆盖运行时世界缓存，并清理临时会话状态。
    /// </summary>
    public void ApplySaveData(GameSaveData data)
    {
        PlayerLocation = data.player?.location_id ?? "player_cafe.doorway";
        NPCs = new List<NpcState>();
        foreach (var savedNpc in data.npcs ?? new List<NpcWorldSaveData>())
        {
            NPCs.Add(new NpcState
            {
                npc_id = savedNpc.npc_id,
                current_location = savedNpc.location_id,
                emotion = savedNpc.emotion,
                energy = savedNpc.energy,
                sociability = savedNpc.sociability,
                current_need = savedNpc.current_need,
            });
        }
        IsDialogueActive = false;
        CurrentDialogueNpcId = null;
        IsSleeping = false;
        IsGameplayReady = true;
        _worldRevision = data.world_revision;
        _restoreDailySchedules?.Invoke(data);
    }

    /// <summary>
    /// 标记玩家正式对话开始。
    /// </summary>
    public void BeginDialogue(string npcId)
    {
        IsDialogueActive = true;
        CurrentDialogueNpcId = npcId;
    }

    /// <summary>
    /// 判断指定 NPC 是否允许关闭当前正式对话。
    /// </summary>
    public bool CanCloseDialogue(string npcId)
    {
        return string.IsNullOrEmpty(npcId)
            || string.IsNullOrEmpty(CurrentDialogueNpcId)
            || npcId == CurrentDialogueNpcId;
    }

    /// <summary>
    /// 清空玩家正式对话状态。
    /// </summary>
    public void CloseDialogue()
    {
        IsDialogueActive = false;
        CurrentDialogueNpcId = null;
    }

    /// <summary>
    /// 按 npc_id 查询当前缓存的 NPC 状态。
    /// </summary>
    public NpcState FindNpc(string npcId)
    {
        return NPCs.Find(n => n.npc_id == npcId);
    }
}
