using NUnit.Framework;
using UnityEngine;

public class GameCommandSenderTests
{
    /// <summary>V2 reader 必须解析两个有序队列，且普通任务不含精确时间点。</summary>
    [Test]
    public void NpcDayPlanReady_ParsesTwoSegmentQueues()
    {
        const string json = "{\"type\":\"NPC_DAY_PLAN_READY\",\"operation_id\":\"op-1\",\"npc_id\":\"npc-1\",\"game_day\":1,\"plan_revision\":4,\"planner_version\":\"daily_schedule_v2\",\"status\":\"success\",\"segments\":[{\"segment_id\":\"work\",\"starts_at\":\"08:00\",\"ends_at\":\"17:00\",\"boundary_policy\":\"active_task_continues\"},{\"segment_id\":\"rest\",\"starts_at\":\"17:00\",\"ends_at\":\"24:00\",\"boundary_policy\":\"force_terminal_at_day_end\"}],\"work_tasks\":[{\"task_id\":\"w1\",\"candidate_id\":\"w1\",\"action_id\":\"read\",\"location_id\":\"bookstore.reading_area\",\"segment_id\":\"work\",\"completion_policy_id\":\"duration\",\"interrupt_policy\":\"fully_interruptible\",\"duration_gameplay_seconds\":60}],\"rest_tasks\":[]}";

        NpcDailyScheduleReadyMsg message = JsonUtility.FromJson<NpcDailyScheduleReadyMsg>(json);

        Assert.That(message.plan_revision, Is.EqualTo(4));
        Assert.That(message.work_tasks, Has.Count.EqualTo(1));
        Assert.That(message.work_tasks[0].segment_id, Is.EqualTo("work"));
        Assert.That(message.rest_tasks, Is.Empty);
    }
}
