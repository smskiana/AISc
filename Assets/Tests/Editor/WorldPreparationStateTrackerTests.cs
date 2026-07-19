using NUnit.Framework;

public sealed class WorldPreparationStateTrackerTests
{
    /// <summary>
    /// 进度消息建立活动 operation，并保留协议身份和上下文。
    /// </summary>
    [Test]
    public void ProgressStartsActiveOperation()
    {
        var tracker = new WorldPreparationStateTracker();

        Assert.That(tracker.TryApplyProgress(Progress("operation-a", 0.4f)), Is.True);
        Assert.That(tracker.Snapshot.operation_id, Is.EqualTo("operation-a"));
        Assert.That(tracker.Snapshot.flow, Is.EqualTo("next_day"));
        Assert.That(tracker.Snapshot.is_active, Is.True);
        Assert.That(tracker.Snapshot.target_game_day, Is.EqualTo(2));
    }

    /// <summary>
    /// 匹配成功终包会完成 operation 并清空失败原因。
    /// </summary>
    [Test]
    public void MatchingCompleteTerminatesOperation()
    {
        var tracker = ActiveTracker("operation-a", 0.4f);

        Assert.That(tracker.TryComplete("operation-a"), Is.True);
        Assert.That(tracker.Snapshot.phase, Is.EqualTo("complete"));
        Assert.That(tracker.Snapshot.is_active, Is.False);
        Assert.That(tracker.Snapshot.progress_floor, Is.EqualTo(1f));
        Assert.That(tracker.Snapshot.failure_reason, Is.Empty);
    }

    /// <summary>
    /// 匹配失败终包会失败 operation，并保留已有进度。
    /// </summary>
    [Test]
    public void MatchingFailureTerminatesOperationAndPreservesProgress()
    {
        var tracker = ActiveTracker("operation-a", 0.4f);

        Assert.That(tracker.TryFail("operation-a", "world_preparation_failed"), Is.True);
        Assert.That(tracker.Snapshot.phase, Is.EqualTo("failed"));
        Assert.That(tracker.Snapshot.is_active, Is.False);
        Assert.That(tracker.Snapshot.progress_floor, Is.EqualTo(0.4f));
        Assert.That(tracker.Snapshot.failure_reason, Is.EqualTo("world_preparation_failed"));
    }

    /// <summary>
    /// 迟到终包不能关闭或污染当前活动 operation。
    /// </summary>
    [TestCase(true)]
    [TestCase(false)]
    public void StaleTerminalDoesNotAffectCurrentOperation(bool complete)
    {
        var tracker = ActiveTracker("operation-new", 0.6f);

        var accepted = complete
            ? tracker.TryComplete("operation-old")
            : tracker.TryFail("operation-old", "stale_failure");

        Assert.That(accepted, Is.False);
        Assert.That(tracker.Snapshot.operation_id, Is.EqualTo("operation-new"));
        Assert.That(tracker.Snapshot.is_active, Is.True);
        Assert.That(tracker.Snapshot.failure_reason, Is.Empty);
    }

    /// <summary>
    /// 已终态 operation 的迟到进度不能将其重新置为活动。
    /// </summary>
    [Test]
    public void LateProgressDoesNotReviveTerminalOperation()
    {
        var tracker = ActiveTracker("operation-a", 0.7f);
        Assert.That(tracker.TryComplete("operation-a"), Is.True);

        Assert.That(tracker.TryApplyProgress(Progress("operation-a", 0.8f)), Is.False);
        Assert.That(tracker.Snapshot.phase, Is.EqualTo("complete"));
        Assert.That(tracker.Snapshot.is_active, Is.False);
    }

    /// <summary>
    /// 活动 operation 期间拒绝其他 operation 的进度，避免并发覆盖。
    /// </summary>
    [Test]
    public void OtherProgressDoesNotReplaceActiveOperation()
    {
        var tracker = ActiveTracker("operation-a", 0.3f);

        Assert.That(tracker.TryApplyProgress(Progress("operation-b", 0.1f)), Is.False);
        Assert.That(tracker.Snapshot.operation_id, Is.EqualTo("operation-a"));
    }

    /// <summary>
    /// 创建指定活动 operation 的测试夹具。
    /// </summary>
    private static WorldPreparationStateTracker ActiveTracker(string operationId, float progress)
    {
        var tracker = new WorldPreparationStateTracker();
        Assert.That(tracker.TryApplyProgress(Progress(operationId, progress)), Is.True);
        return tracker;
    }

    /// <summary>
    /// 创建 next-day 世界准备进度消息。
    /// </summary>
    private static WorldPreparationProgressMsg Progress(string operationId, float progress)
    {
        return new WorldPreparationProgressMsg
        {
            operation_id = operationId,
            flow = "next_day",
            phase = "entering_world",
            progress_floor = progress,
            target_game_day = 2,
        };
    }
}
