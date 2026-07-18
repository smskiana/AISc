using System;
using System.IO;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// 显示单个存档的名称、时间、截图和选择状态。
/// </summary>
public sealed class SaveManagementEntryView : MonoBehaviour
{
    [SerializeField] private Button _selectButton;
    [SerializeField] private TMP_Text _nameText;
    [SerializeField] private TMP_Text _detailText;
    [SerializeField] private RawImage _screenshot;
    [SerializeField] private Texture _placeholderTexture;
    [SerializeField] private Outline _selectionFrame;

    private Texture2D _loadedTexture;

    /// <summary>
    /// 绑定存档展示数据与选择动作。
    /// </summary>
    public void Bind(SaveInfo info, Action onSelected)
    {
        if (_nameText != null)
            _nameText.text = info?.display_name ?? "未命名存档";
        if (_detailText != null)
            _detailText.text = info == null
                ? string.Empty
                : $"第{info.game_day}天  {FormatSavedAt(info.saved_at)}";
        if (_selectButton != null)
        {
            _selectButton.onClick.RemoveAllListeners();
            if (onSelected != null)
                _selectButton.onClick.AddListener(() => onSelected());
        }
        LoadScreenshot(info?.screenshot_path);
        SetSelected(false);
    }

    /// <summary>
    /// 切换选中边框表现。
    /// </summary>
    public void SetSelected(bool selected)
    {
        if (_selectionFrame != null)
            _selectionFrame.enabled = selected;
    }

    /// <summary>
    /// 从槽位截图文件加载纹理，失败时使用占位图。
    /// </summary>
    private void LoadScreenshot(string path)
    {
        if (_loadedTexture != null)
            Destroy(_loadedTexture);
        _loadedTexture = null;

        if (!string.IsNullOrWhiteSpace(path) && File.Exists(path))
        {
            try
            {
                var texture = new Texture2D(2, 2, TextureFormat.RGB24, false);
                if (texture.LoadImage(File.ReadAllBytes(path)))
                    _loadedTexture = texture;
                else
                    Destroy(texture);
            }
            catch (Exception)
            {
                _loadedTexture = null;
            }
        }

        if (_screenshot != null)
            _screenshot.texture = _loadedTexture != null ? _loadedTexture : _placeholderTexture;
    }

    /// <summary>
    /// 格式化现实存档时间。
    /// </summary>
    private static string FormatSavedAt(string raw)
    {
        return DateTime.TryParse(raw, out DateTime value) ? value.ToLocalTime().ToString("yyyy-MM-dd HH:mm") : raw ?? string.Empty;
    }

    /// <summary>
    /// 释放运行时加载的截图纹理。
    /// </summary>
    private void OnDestroy()
    {
        if (_loadedTexture != null)
            Destroy(_loadedTexture);
    }
}
