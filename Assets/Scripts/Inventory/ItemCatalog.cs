using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 从共享镜像配置读取背包展示所需的稳定物品元数据。
/// </summary>
public sealed class ItemCatalog
{
    [Serializable]
    private sealed class ItemList
    {
        public ItemDefinition[] items;
    }

    [Serializable]
    public sealed class ItemDefinition
    {
        public string id;
        public string name;
        public string category;
    }

    private readonly Dictionary<string, ItemDefinition> _items = new Dictionary<string, ItemDefinition>(StringComparer.Ordinal);

    /// <summary>
    /// 加载配置并拒绝空 ID、空分类和重复稳定 ID。
    /// </summary>
    public void Load()
    {
        _items.Clear();
        var asset = Resources.Load<TextAsset>("Config/items");
        if (asset == null)
            throw new InvalidOperationException("缺少 Resources/Config/items.json");

        var list = JsonUtility.FromJson<ItemList>(asset.text);
        foreach (var item in list?.items ?? Array.Empty<ItemDefinition>())
        {
            if (string.IsNullOrWhiteSpace(item.id)
                || string.IsNullOrWhiteSpace(item.name)
                || string.IsNullOrWhiteSpace(item.category))
                throw new InvalidOperationException("物品配置必须包含 id、name 和唯一主分类 category");
            if (_items.ContainsKey(item.id))
                throw new InvalidOperationException($"物品稳定 ID 重复: {item.id}");
            _items.Add(item.id, item);
        }
    }

    /// <summary>
    /// 查询指定稳定 ID 的展示定义。
    /// </summary>
    public bool TryGet(string itemId, out ItemDefinition definition)
    {
        return _items.TryGetValue(itemId ?? string.Empty, out definition);
    }
}
