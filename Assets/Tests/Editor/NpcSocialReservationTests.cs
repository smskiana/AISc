using NUnit.Framework;

/// <summary>
/// 验证 Unity 社交 reservation 的原子占用与 request 所有权释放。
/// </summary>
public sealed class NpcSocialReservationTests
{
    /// <summary>
    /// 任一参与者已占用时，新请求失败且不得占用另一方。
    /// </summary>
    [Test]
    public void TryReserveRejectsPairAtomicallyWhenOneNpcIsBusy()
    {
        var reservations = new NpcSocialReservationTable();
        Assert.That(reservations.TryReserve("first", "sakura", "chihaya"), Is.True);

        Assert.That(reservations.TryReserve("second", "kujo", "chihaya"), Is.False);
        Assert.That(reservations.IsReserved("kujo"), Is.False);
        Assert.That(reservations.IsReserved("chihaya"), Is.True);
    }

    /// <summary>
    /// 迟到旧终态不得释放已经属于其他 request 的 reservation。
    /// </summary>
    [Test]
    public void ReleaseOnlyClearsMatchingRequestOwnership()
    {
        var reservations = new NpcSocialReservationTable();
        Assert.That(reservations.TryReserve("active", "sakura", "chihaya"), Is.True);

        reservations.Release("stale", "sakura", "chihaya");
        Assert.That(reservations.IsReserved("sakura"), Is.True);

        reservations.Release("active", "sakura", "chihaya");
        Assert.That(reservations.IsReserved("sakura"), Is.False);
        Assert.That(reservations.IsReserved("chihaya"), Is.False);
    }
}
