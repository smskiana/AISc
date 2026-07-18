using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// 管理存档产品面板的静态控件和列表渲染。
/// </summary>
public sealed class SaveManagementView : MonoBehaviour
{
    [SerializeField] private GameObject _panel;
    [SerializeField] private TMP_Text _titleText;
    [SerializeField] private TMP_InputField _nameInput;
    [SerializeField] private TMP_Text _emptyText;
    [SerializeField] private Transform _contentRoot;
    [SerializeField] private SaveManagementEntryView _entryPrefab;
    [SerializeField] private Button _newButton;
    [SerializeField] private Button _overwriteButton;
    [SerializeField] private Button _renameButton;
    [SerializeField] private Button _deleteButton;
    [SerializeField] private Button _loadButton;
    [SerializeField] private Button _closeButton;

    private readonly List<SaveManagementEntryView> _entries = new List<SaveManagementEntryView>();

    /// <summary>
    /// 绑定固定管理命令。
    /// </summary>
    public void Bind(
        Action createNew,
        Action overwrite,
        Action rename,
        Action delete,
        Action load,
        Action close)
    {
        BindButton(_newButton, createNew);
        BindButton(_overwriteButton, overwrite);
        BindButton(_renameButton, rename);
        BindButton(_deleteButton, delete);
        BindButton(_loadButton, load);
        BindButton(_closeButton, close);
    }

    /// <summary>
    /// 设置面板模式和可见状态。
    /// </summary>
    public void SetVisible(bool visible, bool saveMode)
    {
        if (_panel != null)
            _panel.SetActive(visible);
        if (_titleText != null)
            _titleText.text = saveMode ? "保存游戏" : "加载游戏";
        if (_newButton != null) _newButton.gameObject.SetActive(saveMode);
        if (_overwriteButton != null) _overwriteButton.gameObject.SetActive(saveMode);
        if (_renameButton != null) _renameButton.gameObject.SetActive(saveMode);
        if (_deleteButton != null) _deleteButton.gameObject.SetActive(saveMode);
        if (_loadButton != null) _loadButton.gameObject.SetActive(!saveMode);
    }

    public string NameInput => _nameInput == null ? string.Empty : _nameInput.text.Trim();

    /// <summary>
    /// 设置新建或重命名输入框的预填名称。
    /// </summary>
    public void SetNameInput(string value)
    {
        if (_nameInput != null)
            _nameInput.text = value ?? string.Empty;
    }

    /// <summary>
    /// 按服务返回顺序重建存档列表。
    /// </summary>
    public void Render(IReadOnlyList<SaveInfo> saves, Action<int> onSelected)
    {
        ClearEntries();
        bool empty = saves == null || saves.Count == 0;
        if (_emptyText != null)
            _emptyText.gameObject.SetActive(empty);
        if (empty || _entryPrefab == null || _contentRoot == null)
            return;

        for (int index = 0; index < saves.Count; index++)
        {
            int capturedIndex = index;
            var entry = Instantiate(_entryPrefab, _contentRoot);
            entry.Bind(saves[index], () => onSelected?.Invoke(capturedIndex));
            _entries.Add(entry);
        }
    }

    /// <summary>
    /// 更新列表中的唯一选中项。
    /// </summary>
    public void SetSelected(int index)
    {
        for (int entryIndex = 0; entryIndex < _entries.Count; entryIndex++)
            _entries[entryIndex].SetSelected(entryIndex == index);
    }

    /// <summary>
    /// 清理旧列表实例。
    /// </summary>
    private void ClearEntries()
    {
        foreach (var entry in _entries)
            if (entry != null)
                Destroy(entry.gameObject);
        _entries.Clear();
    }

    /// <summary>
    /// 重绑一个固定按钮动作。
    /// </summary>
    private static void BindButton(Button button, Action action)
    {
        if (button == null) return;
        button.onClick.RemoveAllListeners();
        if (action != null) button.onClick.AddListener(() => action());
    }
}
