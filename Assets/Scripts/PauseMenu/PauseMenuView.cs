using System;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// 管理暂停主菜单与设置占位页的静态控件。
/// </summary>
public sealed class PauseMenuView : MonoBehaviour
{
    [SerializeField] private GameObject _mainPanel;
    [SerializeField] private GameObject _settingsPanel;
    [SerializeField] private Button _directExitButton;
    [SerializeField] private Button _saveAndExitButton;
    [SerializeField] private Button _saveButton;
    [SerializeField] private Button _loadButton;
    [SerializeField] private Button _settingsButton;
    [SerializeField] private Button _resumeButton;
    [SerializeField] private Button _quitDesktopButton;

    /// <summary>
    /// 绑定暂停菜单全部固定命令。
    /// </summary>
    public void Bind(
        Action directExit,
        Action saveAndExit,
        Action save,
        Action load,
        Action settings,
        Action resume,
        Action quitDesktop)
    {
        BindButton(_directExitButton, directExit);
        BindButton(_saveAndExitButton, saveAndExit);
        BindButton(_saveButton, save);
        BindButton(_loadButton, load);
        BindButton(_settingsButton, settings);
        BindButton(_resumeButton, resume);
        BindButton(_quitDesktopButton, quitDesktop);
    }

    /// <summary>
    /// 显示或隐藏整个暂停菜单。
    /// </summary>
    public void SetVisible(bool visible)
    {
        if (_mainPanel != null)
            _mainPanel.SetActive(visible);
        if (!visible && _settingsPanel != null)
            _settingsPanel.SetActive(false);
    }

    /// <summary>
    /// 在主菜单和设置占位页之间切换。
    /// </summary>
    public void ShowSettings(bool visible)
    {
        if (_mainPanel != null)
            _mainPanel.SetActive(!visible);
        if (_settingsPanel != null)
            _settingsPanel.SetActive(visible);
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
