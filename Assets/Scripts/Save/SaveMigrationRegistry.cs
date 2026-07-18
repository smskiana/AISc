using System;
using System.Collections.Generic;

/// <summary>
/// 表示一次可替换、可测试的 Unity 存档版本迁移。
/// </summary>
public interface ISaveMigration
{
    int FromVersion { get; }
    int ToVersion { get; }
    GameSaveData Migrate(GameSaveData data);
}

/// <summary>
/// 按版本链执行存档迁移，避免在仓储中累积条件分支。
/// </summary>
public class SaveMigrationRegistry
{
    private readonly Dictionary<int, ISaveMigration> _migrations = new Dictionary<int, ISaveMigration>();

    /// <summary>
    /// 注册项目内连续的正式存档迁移链。
    /// </summary>
    public SaveMigrationRegistry()
    {
        Register(new SaveMigrationV1ToV2());
    }

    /// <summary>
    /// 注册一个起始版本唯一的迁移步骤。
    /// </summary>
    public void Register(ISaveMigration migration)
    {
        if (migration == null) throw new ArgumentNullException(nameof(migration));
        if (migration.ToVersion <= migration.FromVersion)
            throw new ArgumentException("存档迁移目标版本必须大于起始版本");
        _migrations.Add(migration.FromVersion, migration);
    }

    /// <summary>
    /// 将存档按连续迁移链升级到目标版本。
    /// </summary>
    public GameSaveData Migrate(GameSaveData data, int targetVersion)
    {
        if (data == null) throw new ArgumentNullException(nameof(data));
        while (data.schema_version < targetVersion)
        {
            if (!_migrations.TryGetValue(data.schema_version, out var migration))
                throw new InvalidOperationException($"缺少存档迁移: {data.schema_version} -> {targetVersion}");
            data = migration.Migrate(data) ?? throw new InvalidOperationException("存档迁移返回空数据");
            if (data.schema_version != migration.ToVersion)
                throw new InvalidOperationException("存档迁移未写入声明的目标版本");
        }
        return data;
    }
}

/// <summary>
/// 为旧 NPC 世界快照补充显式空日程和 revision 初值。
/// </summary>
public sealed class SaveMigrationV1ToV2 : ISaveMigration
{
    public int FromVersion => 1;
    public int ToVersion => 2;

    /// <summary>
    /// 将缺少日程字段的旧存档升级为可触发当日重新规划的状态。
    /// </summary>
    public GameSaveData Migrate(GameSaveData data)
    {
        foreach (NpcWorldSaveData npc in data.npcs ?? new List<NpcWorldSaveData>())
        {
            npc.schedule_day = 0;
            npc.schedule_revision = 0;
            npc.schedule_planner_version = string.Empty;
            npc.remaining_daily_schedule ??= new List<NpcDailyScheduleItem>();
        }
        data.schema_version = ToVersion;
        return data;
    }
}
