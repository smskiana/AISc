using NUnit.Framework;

/// <summary>
/// 验证多来源暂停在 Gameplay、UI 和 FX 时间域之间保持独立。
/// </summary>
public sealed class PauseTimeDomainTests
{
    /// <summary>
    /// 当前业务暂停来源应冻结世界和 FX，但允许 UI 动效继续。
    /// </summary>
    [Test]
    public void WorldPausePolicyKeepsUiDomainRunning()
    {
        PauseTimeDomain domains = PauseSourcePolicy.GetDomains(PauseSources.Dialogue);

        Assert.IsTrue((domains & PauseTimeDomain.Gameplay) != 0);
        Assert.IsFalse((domains & PauseTimeDomain.UI) != 0);
        Assert.IsTrue((domains & PauseTimeDomain.FX) != 0);
    }

    /// <summary>
    /// 编辑器诊断暂停来源必须复用正式世界暂停策略。
    /// </summary>
    [Test]
    public void DiagnosticsPauseUsesWorldDomains()
    {
        Assert.AreEqual(
            PauseTimeDomain.Gameplay | PauseTimeDomain.FX,
            PauseSourcePolicy.GetDomains(PauseSources.DiagnosticsTest));
    }

    /// <summary>
    /// 跨域来源叠加时，各域应按自己的最后来源独立恢复。
    /// </summary>
    [Test]
    public void DomainsRecoverIndependentlyAfterLastSourceReleases()
    {
        var model = new PauseModel();
        model.Add("world", PauseTimeDomain.Gameplay | PauseTimeDomain.FX);
        model.Add("ui", PauseTimeDomain.UI);

        Assert.IsTrue(model.IsDomainPaused(PauseTimeDomain.Gameplay));
        Assert.IsTrue(model.IsDomainPaused(PauseTimeDomain.UI));
        Assert.IsTrue(model.IsDomainPaused(PauseTimeDomain.FX));

        model.Remove("world");

        Assert.IsFalse(model.IsDomainPaused(PauseTimeDomain.Gameplay));
        Assert.IsTrue(model.IsDomainPaused(PauseTimeDomain.UI));
        Assert.IsFalse(model.IsDomainPaused(PauseTimeDomain.FX));
    }

    /// <summary>
    /// 同一域存在多个来源时，释放其中一个不得提前恢复。
    /// </summary>
    [Test]
    public void DomainStaysPausedUntilEveryAffectingSourceReleases()
    {
        var model = new PauseModel();
        model.Add("first", PauseTimeDomain.Gameplay);
        model.Add("second", PauseTimeDomain.Gameplay);

        model.Remove("first");
        Assert.IsTrue(model.IsDomainPaused(PauseTimeDomain.Gameplay));

        model.Remove("second");
        Assert.IsFalse(model.IsDomainPaused(PauseTimeDomain.Gameplay));
    }
}
