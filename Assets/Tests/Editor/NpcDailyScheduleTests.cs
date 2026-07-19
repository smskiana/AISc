using System;
using System.Collections.Generic;
using System.IO;
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

    /// <summary>
    /// schema 2 存档必须升级到当前 schema 3，并清除旧日程 owner 状态。
    /// </summary>
    [Test]
    public void SaveMigrationV2ToV3_ClearsLegacyScheduleState()
    {
        var data = new GameSaveData
        {
            schema_version = 2,
            npcs = new List<NpcWorldSaveData>
            {
                new NpcWorldSaveData
                {
                    npc_id = "sakura",
                    schedule_day = 1,
                    schedule_revision = 4,
                    schedule_planner_version = "legacy",
                    day_plan = new NpcDayPlan(),
                },
            },
        };

        GameSaveData migrated = new SaveMigrationRegistry().Migrate(data, 3);

        Assert.That(migrated.schema_version, Is.EqualTo(3));
        Assert.That(migrated.npcs[0].day_plan, Is.Null);
        Assert.That(migrated.npcs[0].schedule_day, Is.EqualTo(0));
        Assert.That(migrated.npcs[0].schedule_revision, Is.EqualTo(0));
        Assert.That(migrated.npcs[0].schedule_planner_version, Is.Empty);
        Assert.That(migrated.npcs[0].remaining_daily_schedule, Is.Empty);
    }

    /// <summary>
    /// 当前 schema 的新存档必须能完成 Unity 本地 prepare。
    /// </summary>
    [Test]
    public void UnitySaveRepositoryPrepare_AcceptsCurrentSchema()
    {
        string rootPath = Path.Combine(Path.GetTempPath(), $"aisc_save_test_{Guid.NewGuid():N}");
        try
        {
            var repository = new UnitySaveRepository(rootPath, new SaveMigrationRegistry());
            var data = new GameSaveData
            {
                save_id = "save_auto",
                slot_id = "auto",
                checkpoint_id = "checkpoint_test",
                created_at = "2026-07-19T00:00:00Z",
            };

            SaveManifest manifest = repository.Prepare(data, string.Empty, 1, "auto", true, null);

            Assert.That(manifest.unity_schema_version, Is.EqualTo(3));
        }
        finally
        {
            if (Directory.Exists(rootPath)) Directory.Delete(rootPath, true);
        }
    }

    /// <summary>
    /// 傍晚压缩只能重排未开始候选，并稳定优先保留 required 项。
    /// </summary>
    [Test]
    public void CompressEvening_PrioritizesRequiredRemainingItems()
    {
        var controller = new NpcDailyScheduleController();
        var message = Ready(1, "optional");
        message.items.Add(new NpcDailyScheduleItem { candidate_id = "required", action_id = "work_open", location_id = "flower_shop.doorway", planned_start_time = "17:30", necessity = "required" });
        message.items[0].necessity = "optional";
        controller.TryReplace(message, out _);

        controller.CompressEvening(17, 0);

        Assert.That(controller.Remaining[0].candidate_id, Is.EqualTo("required"));
        Assert.That(controller.EveningCompressed, Is.True);
    }

    /// <summary>
    /// 傍晚压缩丢弃已过窗口的非必需项，但保留 required 供显式恢复裁决。
    /// </summary>
    [Test]
    public void CompressEvening_DropsExpiredOptionalButKeepsRequired()
    {
        var controller = new NpcDailyScheduleController();
        var message = Ready(1, "expired_optional");
        message.items[0].planned_start_time = "15:00";
        message.items[0].necessity = "optional";
        message.items.Add(new NpcDailyScheduleItem { candidate_id = "expired_required", action_id = "work_open", location_id = "flower_shop.doorway", planned_start_time = "15:00", necessity = "required", miss_policy = "request_replan" });
        controller.TryReplace(message, out _);

        controller.CompressEvening(17, 0);

        Assert.That(controller.Remaining.Count, Is.EqualTo(1));
        Assert.That(controller.Remaining[0].candidate_id, Is.EqualTo("expired_required"));
        Assert.That(controller.CompressionBeforeCount, Is.EqualTo(2));
        Assert.That(controller.CompressionAfterCount, Is.EqualTo(1));
    }

    /// <summary>相同 NPC、游戏日和 base revision 只能创建一个 pending。</summary>
    [Test]
    public void ReplanTracker_EnforcesSingleFlightAndMatchingTerminal()
    {
        float now = 1f;
        var tracker = new NpcScheduleReplanTracker(() => now, 10f);
        var snapshot = new NpcScheduleSnapshotReference { snapshot_id = "s1", game_day = 1, time_revision = 2, world_revision = 3 };
        Assert.That(tracker.TryBegin("sakura", 1, 4, snapshot, new GameTime { day = 1 }, out var pending, out _), Is.True);
        Assert.That(tracker.TryBegin("sakura", 1, 4, snapshot, new GameTime { day = 1 }, out _, out string duplicate), Is.False);
        Assert.That(duplicate, Is.EqualTo("replan_already_in_flight"));
        Assert.That(tracker.TryAcceptTerminal(new NpcDailyScheduleReadyMsg { npc_id = "sakura", operation_id = "late", status = "failed" }, out _), Is.False);
        Assert.That(tracker.TryAcceptTerminal(new NpcDailyScheduleReadyMsg { npc_id = "sakura", operation_id = pending.operation_id, status = "failed", failure_reason = "stable_failure" }, out string terminal), Is.True);
        Assert.That(terminal, Is.EqualTo("stable_failure"));
    }

    /// <summary>超时和跨日取消都必须释放 pending，允许后续重新申请。</summary>
    [Test]
    public void ReplanTracker_ExpiresAndCancelsPreviousDay()
    {
        float now = 1f;
        var tracker = new NpcScheduleReplanTracker(() => now, 10f);
        var day1 = new NpcScheduleSnapshotReference { snapshot_id = "s1", game_day = 1 };
        tracker.TryBegin("sakura", 1, 1, day1, new GameTime { day = 1 }, out _, out _);
        now = 12f;
        tracker.GetDiagnostic("sakura", out _, out string timeout);
        Assert.That(timeout, Is.EqualTo("schedule_replan_timeout"));
        tracker.TryBegin("sakura", 1, 1, day1, new GameTime { day = 1 }, out _, out _);
        tracker.CancelBeforeDay(2);
        tracker.GetDiagnostic("sakura", out _, out string cancelled);
        Assert.That(cancelled, Is.EqualTo("previous_day_replan_cancelled"));
    }

    /// <summary>两段式 runtime 只在匹配终态后推进，且工作队列提前耗尽不会提前进入休息段。</summary>
    [Test]
    public void DayPlanRuntime_ConsumesMatchingTerminalWithoutEarlySegmentSwitch()
    {
        var runtime = new NpcDayPlanRuntime();
        Assert.That(runtime.AcceptPlan(DayPlan(), out _), Is.True);
        Assert.That(runtime.ActiveTask.task_id, Is.EqualTo("work_1"));
        Assert.That(runtime.OnTaskTerminal("other", "succeeded", out string mismatch), Is.False);
        Assert.That(mismatch, Is.EqualTo("terminal_task_mismatch"));
        Assert.That(runtime.OnTaskTerminal("work_1", "failed", out _), Is.True);
        Assert.That(runtime.ActiveTask, Is.Null);
        Assert.That(runtime.ActiveSegmentId, Is.EqualTo("work"));

        Assert.That(runtime.OnSegmentBoundary("work_end", out string boundary), Is.True);
        Assert.That(boundary, Is.EqualTo("rest_segment_started"));
        Assert.That(runtime.ActiveTask.task_id, Is.EqualTo("rest_1"));
    }

    /// <summary>17:00 保留当前工作但退役其余工作，终态后再启动休息队首。</summary>
    [Test]
    public void DayPlanRuntime_WorkBoundaryKeepsActiveAndRetiresRemaining()
    {
        var plan = DayPlan();
        plan.work_tasks.Add(Task("work_2", "work", "work_clean", "candidate_work_2"));
        var runtime = new NpcDayPlanRuntime();
        runtime.AcceptPlan(plan, out _);

        runtime.OnSegmentBoundary("work_end", out string boundary);
        Assert.That(boundary, Is.EqualTo("work_task_continues_after_segment"));
        Assert.That(runtime.RemainingWork, Is.Empty);
        Assert.That(runtime.ActiveTask.task_id, Is.EqualTo("work_1"));
        runtime.OnTaskTerminal("work_1", "cancelled", out _);
        Assert.That(runtime.ActiveSegmentId, Is.EqualTo("rest"));
        Assert.That(runtime.ActiveTask.task_id, Is.EqualTo("rest_1"));
    }

    /// <summary>午夜强制终态并清空剩余队列，使日终不再等待活动任务。</summary>
    [Test]
    public void DayPlanRuntime_DayBoundaryForcesTerminalAndClosesDay()
    {
        var runtime = new NpcDayPlanRuntime();
        runtime.AcceptPlan(DayPlan(), out _);
        runtime.OnSegmentBoundary("day_end", out string boundary);
        NpcDayPlanRuntimeSnapshot snapshot = runtime.CreateSnapshot();

        Assert.That(boundary, Is.EqualTo("retired_at_day_end"));
        Assert.That(snapshot.day_closed, Is.True);
        Assert.That(snapshot.active_task, Is.Null);
        Assert.That(snapshot.last_terminal_reason, Is.EqualTo("forced_terminal_at_day_boundary"));
        Assert.That(snapshot.remaining_work_count, Is.Zero);
        Assert.That(snapshot.remaining_rest_count, Is.Zero);
    }

    /// <summary>revision 冲突、迟到变更和不可抢占任务均返回稳定原因。</summary>
    [Test]
    public void DayPlanRuntime_RejectsRevisionConflictLateMutationAndNonInterruptiblePreempt()
    {
        var plan = DayPlan();
        plan.work_tasks[0].interrupt_policy = "non_interruptible";
        var runtime = new NpcDayPlanRuntime();
        Assert.That(runtime.AcceptPlan(plan, out _), Is.True);
        NpcDayPlan conflict = DayPlan();
        conflict.work_tasks[0].location_id = "flower_shop.counter";
        Assert.That(runtime.AcceptPlan(conflict, out string conflictReason), Is.False);
        Assert.That(conflictReason, Is.EqualTo("revision_content_conflict"));

        var mutation = Mutation("preempt_current", 1);
        Assert.That(runtime.ApplyMutation(mutation, Task("mutated", "work", "work_clean", "candidate_mutation"), out string blocked), Is.False);
        Assert.That(blocked, Is.EqualTo("current_task_not_interruptible"));
        runtime.OnSegmentBoundary("day_end", out _);
        NpcTaskMutation lateMutation = Mutation("append_after_current", 1);
        lateMutation.operation_id = "late-mutation-op";
        Assert.That(runtime.ApplyMutation(lateMutation, Task("late", "work", "work_clean", "candidate_mutation"), out string late), Is.False);
        Assert.That(late, Is.EqualTo("mutation_arrived_after_day_end"));
    }

    /// <summary>玩家可抢占任务默认退役旧任务，且不会把旧任务隐式重新入队。</summary>
    [Test]
    public void DayPlanRuntime_PlayerPreemptRetiresPreviousTask()
    {
        var runtime = new NpcDayPlanRuntime();
        runtime.AcceptPlan(DayPlan(), out _);
        Assert.That(runtime.ApplyMutation(
            Mutation("preempt_current", 1),
            Task("mutated", "work", "work_clean", "candidate_mutation"),
            out string reason), Is.True);

        Assert.That(reason, Is.EqualTo("mutation_preempted_current"));
        Assert.That(runtime.ActiveTask.task_id, Is.EqualTo("mutated"));
        Assert.That(runtime.PlanRevision, Is.EqualTo(2));
        Assert.That(runtime.CreateSnapshot().last_terminal_reason, Is.EqualTo("preempted_by_player"));
        Assert.That(runtime.RemainingWork, Is.Empty);
        Assert.That(runtime.ApplyMutation(
            Mutation("preempt_current", 1),
            Task("duplicate", "work", "work_clean", "candidate_mutation"),
            out string duplicateReason), Is.True);
        Assert.That(duplicateReason, Is.EqualTo("mutation_preempted_current"));
        Assert.That(runtime.ActiveTask.task_id, Is.EqualTo("mutated"));
        Assert.That(runtime.PlanRevision, Is.EqualTo(2));
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

    private static NpcDayPlan DayPlan()
    {
        return new NpcDayPlan
        {
            operation_id = "plan-op",
            npc_id = "sakura",
            game_day = 1,
            plan_revision = 1,
            planner_version = "test-v2",
            segments = new List<NpcPlanSegmentDefinition>
            {
                new NpcPlanSegmentDefinition { segment_id = "work", starts_at = "08:00", ends_at = "17:00", boundary_policy = "finish_active_then_retire" },
                new NpcPlanSegmentDefinition { segment_id = "rest", starts_at = "17:00", ends_at = "24:00", boundary_policy = "force_terminal_at_day_end" },
            },
            work_tasks = new List<NpcPlannedTask> { Task("work_1", "work", "work_tend", "candidate_work_1") },
            rest_tasks = new List<NpcPlannedTask> { Task("rest_1", "rest", "rest", "candidate_rest_1") },
        };
    }

    private static NpcPlannedTask Task(string taskId, string segmentId, string actionId, string candidateId)
    {
        return new NpcPlannedTask
        {
            task_id = taskId,
            candidate_id = candidateId,
            action_id = actionId,
            location_id = "flower_shop.back_room",
            segment_id = segmentId,
            completion_policy_id = "duration",
            interrupt_policy = "player_interruptible",
            duration_gameplay_seconds = 60,
            source = "test",
        };
    }

    private static NpcTaskMutation Mutation(string mutationType, long baseRevision)
    {
        return new NpcTaskMutation
        {
            operation_id = "mutation-op",
            npc_id = "sakura",
            base_plan_revision = baseRevision,
            source_type = "player_dialogue",
            mutation_type = mutationType,
            candidate_id = "candidate_mutation",
            requested_segment = "work",
        };
    }
}
