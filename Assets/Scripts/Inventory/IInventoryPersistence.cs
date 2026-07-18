using System.Collections.Generic;

/// <summary>
/// 隔离存档服务与背包控制器的持久化契约。
/// </summary>
public interface IInventoryPersistence
{
    List<InventoryEntrySaveData> CaptureInventory();
    void RestoreInventory(IEnumerable<InventoryEntrySaveData> entries);
}
