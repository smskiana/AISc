using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

/// <summary>
/// 开始界面视图：持有 UI 引用，并负责列表渲染与显隐。
/// </summary>
public class StartMenuView : MonoBehaviour
{
    [SerializeField] private Canvas _canvas;
    [SerializeField] private TMP_Text _statusLabel;
    [SerializeField] private TMP_Text _saveListEmptyLabel;
    [SerializeField] private TMP_InputField _nameInputField;
    [SerializeField] private Button _loginButton;
    [SerializeField] private Button _newGameButton;
    [SerializeField] private Button _refreshSavesButton;
    [SerializeField] private Button _retryBackendButton;
    [SerializeField] private Button _quitDesktopButton;
    [SerializeField] private Transform _saveListContentRoot;
    [SerializeField] private StartMenuSaveButtonView _saveButtonPrefab;

    private readonly List<StartMenuSaveButtonView> _spawnedSaveButtons = new();

    /// <summary>
    /// 绑定固定按钮事件。
    /// </summary>
    public void BindStaticActions(
        UnityAction onLogin,
        UnityAction onRetryBackend,
        UnityAction onRefreshSaves,
        UnityAction onNewGame,
        UnityAction onQuitDesktop)
    {
        RebindButton(_loginButton, onLogin);
        RebindButton(_retryBackendButton, onRetryBackend);
        RebindButton(_refreshSavesButton, onRefreshSaves);
        RebindButton(_newGameButton, onNewGame);
        RebindButton(_quitDesktopButton, onQuitDesktop);
    }

    public void SetPlayerName(string playerName)
    {
        if (_nameInputField != null)
            _nameInputField.text = playerName;
    }

    public string GetPlayerName()
    {
        if (_nameInputField == null || string.IsNullOrWhiteSpace(_nameInputField.text))
            return "小李";

        return _nameInputField.text.Trim();
    }

    public void SetStatus(string text)
    {
        if (_statusLabel != null)
            _statusLabel.text = text;
    }

    public void SetVisible(bool visible)
    {
        if (_canvas != null)
            _canvas.gameObject.SetActive(visible);
        else
            gameObject.SetActive(visible);
    }

    public void SetButtonsInteractable(bool enabled = true, bool partial = false)
    {
        bool interactable = enabled || partial;
        SetButtonInteractable(_loginButton, interactable);
        SetButtonInteractable(_retryBackendButton, interactable);
        SetButtonInteractable(_refreshSavesButton, interactable);
        SetButtonInteractable(_newGameButton, interactable);
        SetButtonInteractable(_quitDesktopButton, interactable);

        foreach (var buttonView in _spawnedSaveButtons)
        {
            if (buttonView != null)
                buttonView.SetInteractable(interactable);
        }
    }

    /// <summary>
    /// 渲染存档按钮列表。
    /// </summary>
    public void RenderSaveList(List<SaveInfo> saves, bool hasRequestedSaves, Action<string> onLoadClicked)
    {
        ClearSaveButtons();

        bool hasSaves = saves != null && saves.Count > 0;
        if (_saveListEmptyLabel != null)
        {
            _saveListEmptyLabel.gameObject.SetActive(!hasSaves);
            _saveListEmptyLabel.text = hasSaves
                ? string.Empty
                : hasRequestedSaves ? "当前没有可用存档。" : "连接后将显示存档列表。";
        }

        if (!hasSaves || _saveListContentRoot == null || _saveButtonPrefab == null)
            return;

        foreach (var save in saves)
        {
            if (save == null) continue;

            string slot = save.slot;
            string autoLabel = save.is_auto ? "[自动] " : string.Empty;
            string label = $"{autoLabel}{save.display_name}  第{save.game_day}天  {FormatSavedAt(save.saved_at)}";
            var buttonView = Instantiate(_saveButtonPrefab, _saveListContentRoot);
            buttonView.name = $"btn_loadSlot{slot}_st";
            buttonView.Bind(label, () => onLoadClicked?.Invoke(slot));
            _spawnedSaveButtons.Add(buttonView);
        }
    }

    private static string FormatSavedAt(string raw)
    {
        if (DateTime.TryParse(raw, out var dateTime))
            return dateTime.ToString("MM-dd HH:mm");

        return raw ?? string.Empty;
    }

    private void ClearSaveButtons()
    {
        foreach (var buttonView in _spawnedSaveButtons)
        {
            if (buttonView != null)
                Destroy(buttonView.gameObject);
        }

        _spawnedSaveButtons.Clear();
    }

    private static void RebindButton(Button button, UnityAction action)
    {
        if (button == null) return;
        button.onClick.RemoveAllListeners();
        if (action != null)
            button.onClick.AddListener(action);
    }

    private static void SetButtonInteractable(Button button, bool interactable)
    {
        if (button != null)
            button.interactable = interactable;
    }

#if UNITY_EDITOR
    /// <summary>
    /// 编辑器下自动补抓常见引用，降低场景漏绑概率。
    /// </summary>
    private void OnValidate()
    {
        if (_canvas == null)
            _canvas = GetComponent<Canvas>();
    }
#endif
}
