using System;
using System.Collections.Generic;

/// <summary>
/// Unity 权威保存的稳定游戏世界快照。
/// </summary>
[Serializable]
public class GameSaveData
{
    public int schema_version = 3;
    public string save_id;
    public string slot_id;
    public string checkpoint_id;
    public string created_at;
    public long world_revision;
    public GameTime game_time;
    public string weather;
    public PlayerSaveData player = new PlayerSaveData();
    public List<NpcWorldSaveData> npcs = new List<NpcWorldSaveData>();
}

/// <summary>
/// 保存玩家持久游戏事实，不包含场景对象引用。
/// </summary>
[Serializable]
public class PlayerSaveData
{
    public string location_id;
    public List<InventoryEntrySaveData> inventory = new List<InventoryEntrySaveData>();
}

/// <summary>
/// 保存单种物品的稳定 ID 和数量。
/// </summary>
[Serializable]
public class InventoryEntrySaveData
{
    public string item_id;
    public int quantity;
}

/// <summary>
/// 保存 NPC 的世界事实，不保存移动、动画或对话临时状态。
/// </summary>
[Serializable]
public class NpcWorldSaveData
{
    public string npc_id;
    public string location_id;
    public string emotion;
    public float energy;
    public float sociability;
    public bool is_asleep;
    public string current_need;
    public string lingering_concern;
    public int schedule_day;
    public string schedule_planner_version;
    public long schedule_revision;
    public List<NpcDailyScheduleItem> remaining_daily_schedule = new List<NpcDailyScheduleItem>();
    public NpcDayPlan day_plan;
}

/// <summary>
/// 记录 Unity 主存档和 Python 记忆检查点的一致性摘要。
/// </summary>
[Serializable]
public class SaveManifest
{
    public int manifest_version = 1;
    public string save_id;
    public string slot_id;
    public string checkpoint_id;
    public string created_at;
    public string game_build;
    public int unity_schema_version;
    public int memory_schema_version;
    public string world_sha256;
    public string memory_manifest_sha256;
    public string display_name;
    public bool is_auto;
    public string screenshot_file;
}
