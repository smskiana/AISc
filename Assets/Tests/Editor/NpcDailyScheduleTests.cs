using System.Collections.Generic;
using NUnit.Framework;

/// <summary>
/// 验证 Unity 日程 revision、窗口裁决与旧存档迁移。
/// </summary>
public sealed class NpcDailyScheduleTests
{
    /// <summary>
    /// 同 revision 相同内容幂等，不同内容必须拒绝。
    /// </summary>
    [Test]
    public void TryReplace_EnforcesRevisionContentIdentity()
    {
        var controller = new NpcDailyScheduleController();
        var message = Ready(2, "candidate_a");
        Assert.That(controller.TryReplace(message, out _), Is.True);
        Assert.That(controller.TryReplace(message, out string duplicateReason), Is.True);
        Assert.That(duplicateReason, Is.EqualTo("duplicate_schedule_revision"));
        Assert.That(controller.TryReplace(Ready(2, "candidate_b"), out string conflictReason), Is.False);
        Assert.That(conflictReason, Is.EqualTo("revision_content_conflict"));
        Assert.That(controller.TryReplace(Ready(1, "candidate_a"), out string staleReason), Is.False);
        Assert.That(staleReason, Is.EqualTo("stale_schedule_revision"));
    }

    /// <summary>
    /// 社交锁在窗口内延迟，窗口结束后按 miss policy 请求重规划。
    /// </summary>
    [Test]
    public void EvaluateNext_DefersLockAndRequestsReplanAfterWindow()
    {
        var controller = new NpcDailyScheduleController();
        controller.TryReplace(Ready(1, "candidate_a"), out _);
        Assert.That(controller.EvaluateNext(10, 0, true).Decision, Is.EqualTo(NpcScheduleSwitchDecision.Defer));
        Assert.That(controller.EvaluateNext(10, 31, true).Decision, Is.EqualTo(NpcScheduleSwitchDecision.RequestReplan));
    }

    /// <summary>
    /// 旧 schema 必须显式补空日程，而不是依赖反序列化默认值。
    /// </summary>
    [Test]
    public void SaveMigrationV1ToV2_AddsEmptyScheduleState()
    {
        var data = new GameSaveData
        {
            schema_version = 1,
            npcs = new List<NpcWorldSaveData> { new NpcWorldSaveData { npc_id = "sakura", remaining_daily_schedule = null } },
        };
        GameSaveData migrated = new SaveMigrationRegistry().Migrate(data, 2);
        Assert.That(migrated.schema_version, Is.EqualTo(2));
        Assert.That(migrated.npcs[0].schedule_day, Is.EqualTo(0));
        Assert.That(migrated.npcs[0].remaining_daily_schedule, Is.Empty);
    }

    private static NpcDailyScheduleReadyMsg Ready(long revision, string candidateId)
    {
        return new NpcDailyScheduleReadyMsg
        {
            npc_id = "sakura",
            game_day = 1,
            schedule_revision = revision,
            planner_version = "test",
            items = new List<NpcDailyScheduleItem>
            {
                new NpcDailyScheduleItem
                {
                    candidate_id = candidateId,
                    action_id = "eat",
                    location_id = "flower_shop.back_room",
                    planned_start_time = "10:00",
                    miss_policy = "request_replan",
                },
            },
        };
    }
}
