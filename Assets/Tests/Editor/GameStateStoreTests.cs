using NUnit.Framework;

/// <summary>
/// 验证 Unity 主循环可交互状态的显式转换。
/// </summary>
public sealed class GameStateStoreTests
{
    /// <summary>
    /// 午夜世界准备成功后应能恢复此前锁定的主循环交互状态。
    /// </summary>
    [Test]
    public void MarkGameplayReadyRestoresInteractionAfterPreparationLock()
    {
        var store = new GameStateStore();

        store.MarkGameplayNotReady();
        store.MarkGameplayReady();

        Assert.IsTrue(store.IsGameplayReady);
    }
}
