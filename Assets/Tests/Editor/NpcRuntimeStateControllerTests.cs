using NUnit.Framework;

/// <summary>
/// 验证 Unity 权威 NPC 运行时状态和 NpcStateEffect revision 校验。
/// </summary>
public sealed class NpcRuntimeStateControllerTests
{
    /// <summary>
    /// base revision 过期的 effect 必须被拒绝，不能改写 Unity 权威状态。
    /// </summary>
    [Test]
    public void TryApplyEffectRejectsStaleBaseRevision()
    {
        var controller = RestoredController();
        bool applied = controller.TryApplyEffect(Effect(baseRevision: 8, energyDelta: -5f), currentWorldRevision: 9);

        Assert.IsFalse(applied);
        Assert.AreEqual("rejected", controller.LastEffectStatus);
        Assert.AreEqual("stale_base_world_revision", controller.LastEffectReason);
        Assert.AreEqual(80f, controller.Energy);
    }

    /// <summary>
    /// revision 匹配时 effect 应用到 Unity 状态，并保留诊断 operation id。
    /// </summary>
    [Test]
    public void TryApplyEffectAppliesMatchingRevision()
    {
        var controller = RestoredController();
        bool applied = controller.TryApplyEffect(Effect(baseRevision: 9, energyDelta: -5f), currentWorldRevision: 9);

        Assert.IsTrue(applied);
        Assert.AreEqual("applied", controller.LastEffectStatus);
        Assert.AreEqual("effect_1", controller.LastEffectOperationId);
        Assert.AreEqual(75f, controller.Energy);
        Assert.AreEqual(54f, controller.Sociability);
        Assert.AreEqual("开心", controller.Emotion);
    }

    /// <summary>
    /// Unity 分钟 tick 应独立产生 P0 睡眠和 tired need。
    /// </summary>
    [Test]
    public void TickOwnsP0AndNeedState()
    {
        var controller = RestoredController(energy: 17f);
        controller.Tick(new GameTime { day = 1, hour = 10, minute = 0 }, "stand");
        Assert.AreEqual("tired", controller.CurrentNeed);

        controller.Tick(new GameTime { day = 1, hour = 23, minute = 0 }, "stand");
        Assert.IsTrue(controller.IsAsleep);
        Assert.AreEqual("sleep", controller.CurrentNeed);
    }

    private static NpcRuntimeStateController RestoredController(float energy = 80f)
    {
        var controller = new NpcRuntimeStateController();
        controller.Restore(new NpcState
        {
            npc_id = "sakura",
            emotion = "平静",
            energy = energy,
            sociability = 50f,
        });
        return controller;
    }

    private static NpcStateEffectMsg Effect(long baseRevision, float energyDelta)
    {
        return new NpcStateEffectMsg
        {
            operation_id = "effect_1",
            npc_id = "sakura",
            base_world_revision = baseRevision,
            field_deltas = new NpcStateEffectDeltas { energy = energyDelta, sociability = 4f },
            field_values = new NpcStateEffectValues { emotion = "开心" },
            reason = "test",
        };
    }
}
