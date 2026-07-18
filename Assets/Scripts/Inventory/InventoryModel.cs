using System;
using System.Collections.Generic;

/// <summary>
/// 保存背包数量并按统一规则生成只读展示快照。
/// </summary>
public sealed class InventoryModel
{
    public sealed class DisplayEntry
    {
        public string ItemId;
        public string Name;
        public string CategoryId;
        public int Quantity;
    }

    private readonly Dictionary<string, int> _quantities = new Dictionary<string, int>(StringComparer.Ordinal);
    private readonly ItemCatalog _catalog;

    public InventoryModel(ItemCatalog catalog)
    {
        _catalog = catalog ?? throw new ArgumentNullException(nameof(catalog));
    }

    /// <summary>
    /// 用存档条目完整覆盖背包，忽略零或负数量。
    /// </summary>
    public void Restore(IEnumerable<InventoryEntrySaveData> entries)
    {
        _quantities.Clear();
        foreach (var entry in entries ?? Array.Empty<InventoryEntrySaveData>())
        {
            if (entry == null || string.IsNullOrWhiteSpace(entry.item_id) || entry.quantity <= 0)
                continue;
            if (!_catalog.TryGet(entry.item_id, out _))
                continue;
            _quantities[entry.item_id] = entry.quantity;
        }
    }

    /// <summary>
    /// 设置单个物品数量，为后续获得、使用和摧毁命令保留统一写入口。
    /// </summary>
    public void SetQuantity(string itemId, int quantity)
    {
        if (!_catalog.TryGet(itemId, out _))
            throw new ArgumentException($"未知物品 ID: {itemId}", nameof(itemId));
        if (quantity <= 0)
            _quantities.Remove(itemId);
        else
            _quantities[itemId] = quantity;
    }

    /// <summary>
    /// 导出按稳定 ID 排列的存档条目。
    /// </summary>
    public List<InventoryEntrySaveData> CreateSaveEntries()
    {
        var itemIds = new List<string>(_quantities.Keys);
        itemIds.Sort(StringComparer.Ordinal);
        var result = new List<InventoryEntrySaveData>(itemIds.Count);
        foreach (string itemId in itemIds)
            result.Add(new InventoryEntrySaveData { item_id = itemId, quantity = _quantities[itemId] });
        return result;
    }

    /// <summary>
    /// 按主分类、名称、数量和稳定 ID 全部升序生成展示条目。
    /// </summary>
    public List<DisplayEntry> CreateDisplayEntries()
    {
        var result = new List<DisplayEntry>();
        foreach (var pair in _quantities)
        {
            if (!_catalog.TryGet(pair.Key, out ItemCatalog.ItemDefinition definition))
                continue;
            result.Add(new DisplayEntry
            {
                ItemId = pair.Key,
                Name = definition.name,
                CategoryId = definition.category,
                Quantity = pair.Value,
            });
        }

        result.Sort(CompareDisplayEntries);
        return result;
    }

    /// <summary>
    /// 实现背包产品要求的四级稳定升序比较。
    /// </summary>
    private static int CompareDisplayEntries(DisplayEntry left, DisplayEntry right)
    {
        int category = string.Compare(left.CategoryId, right.CategoryId, StringComparison.Ordinal);
        if (category != 0) return category;
        int name = string.Compare(left.Name, right.Name, StringComparison.Ordinal);
        if (name != 0) return name;
        int quantity = left.Quantity.CompareTo(right.Quantity);
        if (quantity != 0) return quantity;
        return string.Compare(left.ItemId, right.ItemId, StringComparison.Ordinal);
    }
}
