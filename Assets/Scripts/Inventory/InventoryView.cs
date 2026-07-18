using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;

/// <summary>
/// 使用资产化分类标题和条目 Prefab 渲染只读背包。
/// </summary>
public sealed class InventoryView : MonoBehaviour
{
    private static readonly Dictionary<string, string> CategoryNames = new Dictionary<string, string>(StringComparer.Ordinal)
    {
        { "drink", "饮品" },
        { "flower", "花卉" },
        { "food", "食物" },
        { "other", "其他" },
    };

    [SerializeField] private GameObject _panel;
    [SerializeField] private Transform _contentRoot;
    [SerializeField] private TMP_Text _emptyText;
    [SerializeField] private GameObject _categoryHeaderPrefab;
    [SerializeField] private GameObject _entryPrefab;

    private readonly List<GameObject> _spawned = new List<GameObject>();

    /// <summary>
    /// 切换背包面板显隐。
    /// </summary>
    public void SetVisible(bool visible)
    {
        if (_panel != null)
            _panel.SetActive(visible);
    }

    /// <summary>
    /// 清理旧内容并按排序后的条目逐分类渲染。
    /// </summary>
    public void Render(IReadOnlyList<InventoryModel.DisplayEntry> entries)
    {
        ClearSpawned();
        bool isEmpty = entries == null || entries.Count == 0;
        if (_emptyText != null)
            _emptyText.gameObject.SetActive(isEmpty);
        if (isEmpty)
            return;

        string currentCategory = null;
        foreach (var entry in entries)
        {
            if (!string.Equals(currentCategory, entry.CategoryId, StringComparison.Ordinal))
            {
                currentCategory = entry.CategoryId;
                SpawnText(_categoryHeaderPrefab, ResolveCategoryName(currentCategory));
            }
            SpawnText(_entryPrefab, $"{entry.Name}  x{entry.Quantity}");
        }
    }

    /// <summary>
    /// 实例化一个文本 Prefab 并写入显示内容。
    /// </summary>
    private void SpawnText(GameObject prefab, string value)
    {
        if (prefab == null || _contentRoot == null)
            return;
        var instance = Instantiate(prefab, _contentRoot);
        var label = instance.GetComponentInChildren<TMP_Text>(true);
        if (label != null)
            label.text = value;
        instance.SetActive(true);
        _spawned.Add(instance);
    }

    /// <summary>
    /// 将内部分类 ID 转换为玩家显示名。
    /// </summary>
    private static string ResolveCategoryName(string categoryId)
    {
        return CategoryNames.TryGetValue(categoryId ?? string.Empty, out string displayName)
            ? displayName
            : "其他";
    }

    /// <summary>
    /// 销毁上次渲染生成的动态条目。
    /// </summary>
    private void ClearSpawned()
    {
        foreach (var instance in _spawned)
            if (instance != null)
                Destroy(instance);
        _spawned.Clear();
    }
}
