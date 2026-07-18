using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using UnityEngine.EventSystems;

/// <summary>
/// 立绘对话 UI（Mode A）—— 点击 NPC 对话时显示。
/// 挂载在 Screen Space Overlay Canvas 上。
///
/// 预制体结构（用户搭建）:
///   DialogueCanvas (Canvas, Screen Space Overlay, sortingOrder=100)
///   ├── BG_Image (Image, 全屏背景)
///   ├── PortraitPanel
///   │   ├── PortraitImage (Image, NPC 立绘)
///   │   └── NameLabel (TMP_Text, NPC 名字, 左上角)
///   ├── DialoguePanel
///   │   ├── DialogueBG (Image, 半透明黑底)
///   │   ├── DialogueText (TMP_Text, 对话内容)
///   │   └── NPCNameLabel (TMP_Text, 说话者名字)
///   └── ChoicesPanel
///       └── ChoiceButton (prefab, 动态生成)
/// </summary>
public class PortraitDialogueUI : MonoBehaviour
{
    [Header("数据")]
    [SerializeField] private LocationBackgroundData _backgroundData;
    [SerializeField] private NpcPortraitData[] _portraitDatas;

    [Header("背景")]
    [SerializeField] private Image _bgImage;

    [Header("立绘")]
    [SerializeField] private Image _portraitImage;
    [SerializeField] private TMP_Text _portraitNameLabel;

    [Header("对话框")]
    [SerializeField] private GameObject _dialoguePanel;
    [SerializeField] private TMP_Text _dialogueText;
    [SerializeField] private TMP_Text _speakerNameLabel;

    [Header("选项")]
    [SerializeField] private GameObject _choicesPanel;
    [SerializeField] private Button _choiceButtonPrefab;

    [Header("回复")]
    [SerializeField] private GameObject _replyPanel;
    [SerializeField] private TMP_Text _replyHintLabel;
    [SerializeField] private TMP_InputField _replyInputField;
    [SerializeField] private Button _sendButton;
    [SerializeField] private Button _endDialogueButton;

    [Header("动画")]
    [SerializeField] private float _typewriterSpeed = 0.03f;  // 逐字显示速度
    [Header("加载")]
    [SerializeField] private float _loadingDotInterval = 0.35f;
    [SerializeField] private string _npcReplyLoadingPrefix = "思考中";
    [SerializeField] private string _suggestionLoadingPrefix = "快捷回复生成中";
    [SerializeField] private int _choiceLoadingPlaceholderCount = 3;

    private string _currentNpcId;
    private string _accumulatedText;
    private float _typewriterTimer;
    private int _typewriterIndex;
    private bool _isTyping;
    private bool _isSubscribed;
    private bool _isNpcReplyLoading;
    private bool _isSuggestionLoading;
    private float _npcReplyLoadingTimer;
    private int _npcReplyLoadingDotCount;
    private float _suggestionLoadingTimer;
    private int _suggestionLoadingDotCount;

    private Dictionary<string, NpcPortraitData> _portraitMap;
    private readonly List<TMP_Text> _suggestionLoadingLabels = new();

    // ── 初始化 ──

    void Awake()
    {
        EnsureInitialized();
        EnsureUiReferences();

        gameObject.SetActive(false);
    }

    void OnEnable()
    {
        EnsureSubscribed();
    }

    void Update()
    {
        // 逐字显示
        if (_isTyping && !string.IsNullOrEmpty(_accumulatedText))
        {
            _typewriterTimer += PauseClock.GetDeltaTime(PauseTimeDomain.UI);
            while (_typewriterTimer >= _typewriterSpeed && _typewriterIndex < _accumulatedText.Length)
            {
                _typewriterTimer -= _typewriterSpeed;
                _typewriterIndex++;
                _dialogueText.text = _accumulatedText[.._typewriterIndex];
            }
            if (_typewriterIndex >= _accumulatedText.Length)
                _isTyping = false;
        }

        UpdateLoadingAnimations();

        if (!gameObject.activeInHierarchy) return;

        if (Input.GetKeyDown(KeyCode.Escape))
        {
            RequestEndDialogue();
        }

        if (_replyInputField != null
            && _replyPanel != null
            && _replyPanel.activeInHierarchy
            && _replyInputField.isFocused
            && (Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter)))
        {
            SubmitCurrentReply();
        }
    }

    void OnDisable()
    {
        TryUnsubscribe();
    }

    void OnDestroy()
    {
        TryUnsubscribe();
    }

    // ── 公开 API ──

    /// <summary>打开对话 UI</summary>
    public void Open(string npcId, string location, string npcEmotion = "平静")
    {
        EnsureInitialized();
        EnsureSubscribed();
        EnsureUiReferences();
        _currentNpcId = npcId;

        // 背景
        if (_bgImage != null && _backgroundData != null)
        {
            var bg = _backgroundData.GetBackground(location);
            if (bg != null) _bgImage.sprite = bg;
        }

        // 立绘
        var data = GetPortraitData(npcId);
        if (_portraitImage != null && data != null)
        {
            _portraitImage.sprite = data.GetPortrait(npcEmotion);
            _portraitImage.enabled = true;
        }
        if (_portraitNameLabel != null && data != null)
            _portraitNameLabel.text = data.NpcName;

        // 对话框
        if (_dialoguePanel != null) _dialoguePanel.SetActive(true);
        if (_speakerNameLabel != null && data != null) _speakerNameLabel.text = data.NpcName;
        ResetNpcReplyText();
        StartNpcReplyLoading();

        // 选项
        SetChoicesVisible(false);
        SetReplyPanelVisible(false);
        ClearReplyInput();

        gameObject.SetActive(true);
    }

    /// <summary>关闭对话 UI</summary>
    public void Close()
    {
        StopNpcReplyLoading(clearDisplay: false);
        StopSuggestionLoading(clearPlaceholders: true);
        SetChoicesVisible(false);
        SetReplyPanelVisible(false);
        ClearReplyInput();
        ResetNpcReplyText();
        gameObject.SetActive(false);
        _currentNpcId = null;
    }

    /// <summary>追加对话 token（后台推流）</summary>
    public void AppendToken(string token)
    {
        if (_isNpcReplyLoading)
            StopNpcReplyLoading(clearDisplay: true);

        SetReplyPanelVisible(false);
        SetChoicesVisible(false);
        _accumulatedText = FormatNpcReplyForDisplay(_accumulatedText + token);
        _typewriterIndex = Mathf.Min(_typewriterIndex, _accumulatedText.Length);
        _isTyping = true;
    }

    /// <summary>本轮 NPC 回复结束，开放玩家输入并按需显示选项。</summary>
    public void ShowChoices(List<string> choices)
    {
        OnNpcReplyComplete(_accumulatedText, choices);
    }

    /// <summary>
    /// 当前这轮 NPC 已说完，显示回复输入区。
    /// </summary>
    public void OnNpcReplyComplete(string fullNpcReply, List<string> choices)
    {
        EnsureUiReferences();
        _isTyping = false;
        StopNpcReplyLoading(clearDisplay: false);

        if (!string.IsNullOrWhiteSpace(fullNpcReply))
            _accumulatedText = FormatNpcReplyForDisplay(fullNpcReply);

        if (_dialogueText != null)
            _dialogueText.text = _accumulatedText;

        SetReplyPanelVisible(true);
        ApplySuggestionChoices(choices, startLoadingIfEmpty: true);
        FocusReplyInput();
    }

    /// <summary>
    /// 在 NPC 回复结束后，用真正生成完成的快捷回复替换加载占位。
    /// </summary>
    public void UpdateSuggestionChoices(List<string> choices)
    {
        EnsureUiReferences();
        ApplySuggestionChoices(choices, startLoadingIfEmpty: false);
        SetReplyPanelVisible(true);
        FocusReplyInput();
    }

    void OnChoiceClicked(string choice)
    {
        SubmitReply(choice);
    }

    /// <summary>
    /// 点击发送按钮后提交玩家输入。
    /// </summary>
    void OnSendButtonClicked()
    {
        SubmitCurrentReply();
    }

    /// <summary>
    /// 点击结束按钮或按 Esc 时结束对话。
    /// </summary>
    void OnEndDialogueButtonClicked()
    {
        RequestEndDialogue();
    }

    // ── 事件 ──

    void HandleDialogueToken(DialogueTokenMsg msg)
    {
        if (msg.npc_id != _currentNpcId) return;
        AppendToken(msg.token);
    }

    // ── 辅助 ──

    NpcPortraitData GetPortraitData(string npcId)
    {
        EnsureInitialized();
        _portraitMap.TryGetValue(npcId, out var d);
        if (d == null)
            Debug.LogWarning($"[PortraitDialogueUI] 未找到 npc_id={npcId} 的立绘配置");
        return d;
    }

    /// <summary>
    /// 确保立绘字典在 UI 首次被直接调用时也能完成初始化。
    /// </summary>
    void EnsureInitialized()
    {
        if (_portraitMap != null) return;

        _portraitMap = new();
        if (_portraitDatas == null) return;

        foreach (var p in _portraitDatas)
        {
            if (p != null)
                _portraitMap[p.NpcId] = p;
        }
    }

    /// <summary>
    /// 确保对话 token 事件已订阅，避免 UI 初始隐藏时错过 Start/Awake 生命周期。
    /// </summary>
    void EnsureSubscribed()
    {
        if (_isSubscribed) return;

        var gm = GameManager.Instance;
        if (gm == null) return;

        gm.OnDialogueToken += HandleDialogueToken;
        _isSubscribed = true;
    }

    /// <summary>
    /// 在 UI 关闭或销毁时安全取消事件订阅。
    /// </summary>
    void TryUnsubscribe()
    {
        if (!_isSubscribed) return;

        var gm = GameManager.Instance;
        if (gm != null)
            gm.OnDialogueToken -= HandleDialogueToken;

        _isSubscribed = false;
    }

    /// <summary>
    /// 从现有场景层级中补齐回复区引用，不负责运行时创建 UI 布局。
    /// </summary>
    void EnsureUiReferences()
    {
        if (_replyPanel == null)
        {
            var existing = transform.Find("pnl_reply_dy");
            if (existing != null)
                _replyPanel = existing.gameObject;
        }

        if (_replyPanel != null && _replyInputField == null)
            _replyInputField = _replyPanel.GetComponentInChildren<TMP_InputField>(true);

        if (_replyPanel != null && _replyHintLabel == null)
        {
            var hintTransform = _replyPanel.transform.Find("txt_replyHint_dy");
            if (hintTransform != null)
                _replyHintLabel = hintTransform.GetComponent<TMP_Text>();
        }

        if (_replyPanel != null && _sendButton == null)
        {
            var sendTransform = _replyPanel.transform.Find("btn_send_st");
            if (sendTransform != null)
                _sendButton = sendTransform.GetComponent<Button>();
        }

        if (_replyPanel != null && _endDialogueButton == null)
        {
            var endTransform = _replyPanel.transform.Find("btn_endDialogue_st");
            if (endTransform != null)
                _endDialogueButton = endTransform.GetComponent<Button>();
        }

        BindReplyButtonEvents();
    }

    /// <summary>
    /// 绑定回复区按钮事件，避免重复监听。
    /// </summary>
    void BindReplyButtonEvents()
    {
        if (_sendButton != null)
        {
            _sendButton.onClick.RemoveListener(OnSendButtonClicked);
            _sendButton.onClick.AddListener(OnSendButtonClicked);
        }

        if (_endDialogueButton != null)
        {
            _endDialogueButton.onClick.RemoveListener(OnEndDialogueButtonClicked);
            _endDialogueButton.onClick.AddListener(OnEndDialogueButtonClicked);
        }
    }

    /// <summary>
    /// 清空旧台词，为下一轮 NPC 回复做准备。
    /// </summary>
    void ResetNpcReplyText()
    {
        if (_dialogueText != null)
            _dialogueText.text = "";

        _accumulatedText = "";
        _typewriterTimer = 0f;
        _typewriterIndex = 0;
        _isTyping = false;
    }

    /// <summary>
    /// 将模型回复中的显式换行折叠为空格，避免多段留白撑满固定高度的对话框。
    /// </summary>
    static string FormatNpcReplyForDisplay(string text)
    {
        if (string.IsNullOrWhiteSpace(text)) return string.Empty;

        var builder = new System.Text.StringBuilder(text.Length);
        bool pendingLineBreak = false;
        foreach (char character in text)
        {
            if (character == '\r' || character == '\n')
            {
                pendingLineBreak = true;
                continue;
            }

            if (pendingLineBreak)
            {
                if (char.IsWhiteSpace(character))
                    continue;

                if (builder.Length > 0 && builder[builder.Length - 1] != ' ')
                    builder.Append(' ');
                pendingLineBreak = false;
            }

            builder.Append(character);
        }

        return builder.ToString().Trim();
    }

    /// <summary>
    /// 发送输入框中的玩家回复。
    /// </summary>
    void SubmitCurrentReply()
    {
        if (_replyInputField == null) return;
        SubmitReply(_replyInputField.text);
    }

    /// <summary>
    /// 提交玩家回复，并在发送前清空上一轮 NPC 文本。
    /// </summary>
    void SubmitReply(string replyText)
    {
        if (string.IsNullOrWhiteSpace(replyText)) return;

        var gm = GameManager.Instance;
        if (gm == null || string.IsNullOrEmpty(_currentNpcId)) return;

        PrepareForNextNpcReply();
        gm.SendPlayerChoice(_currentNpcId, replyText.Trim());
    }

    /// <summary>
    /// 玩家发言后，隐藏输入控件并清空旧台词，等待下一轮回复。
    /// </summary>
    void PrepareForNextNpcReply()
    {
        StopSuggestionLoading(clearPlaceholders: true);
        SetChoicesVisible(false);
        SetReplyPanelVisible(false);
        ClearReplyInput();
        ResetNpcReplyText();
        StartNpcReplyLoading();
    }

    /// <summary>
    /// 请求结束当前对话。
    /// </summary>
    void RequestEndDialogue()
    {
        var gm = GameManager.Instance;
        if (gm != null && !string.IsNullOrEmpty(_currentNpcId))
            gm.EndDialogue("player_left");
        else
            Close();
    }

    /// <summary>
    /// 清除旧选项按钮，保留容器本身。
    /// </summary>
    void ClearChoiceButtons()
    {
        if (_choicesPanel == null) return;

        foreach (Transform t in _choicesPanel.transform)
        {
            t.gameObject.SetActive(false);
            Destroy(t.gameObject);
        }

        _suggestionLoadingLabels.Clear();
    }

    /// <summary>
    /// 控制选项区显隐。
    /// </summary>
    void SetChoicesVisible(bool visible)
    {
        if (_choicesPanel != null)
            _choicesPanel.SetActive(visible);
    }

    /// <summary>
    /// 控制回复输入区显隐。
    /// </summary>
    void SetReplyPanelVisible(bool visible)
    {
        if (_replyPanel != null)
            _replyPanel.SetActive(visible);
    }
    /// <summary>
    /// 根据对话当前所处阶段，刷新 NPC 回复与快捷回复的点点点加载动画。
    /// </summary>
    void UpdateLoadingAnimations()
    {
        if (!gameObject.activeInHierarchy) return;

        if (_isNpcReplyLoading)
        {
            _npcReplyLoadingTimer += PauseClock.GetDeltaTime(PauseTimeDomain.UI);
            if (_npcReplyLoadingTimer >= _loadingDotInterval)
            {
                _npcReplyLoadingTimer = 0f;
                _npcReplyLoadingDotCount = NextLoadingDotCount(_npcReplyLoadingDotCount);
                if (_dialogueText != null)
                    _dialogueText.text = BuildLoadingText(_npcReplyLoadingPrefix, _npcReplyLoadingDotCount);
            }
        }

        if (_isSuggestionLoading)
        {
            _suggestionLoadingTimer += PauseClock.GetDeltaTime(PauseTimeDomain.UI);
            if (_suggestionLoadingTimer >= _loadingDotInterval)
            {
                _suggestionLoadingTimer = 0f;
                _suggestionLoadingDotCount = NextLoadingDotCount(_suggestionLoadingDotCount);
                UpdateSuggestionLoadingVisual();
            }
        }
    }

    /// <summary>
    /// 开始显示 NPC 回复生成中的加载态。
    /// </summary>
    void StartNpcReplyLoading()
    {
        _isNpcReplyLoading = true;
        _npcReplyLoadingTimer = 0f;
        _npcReplyLoadingDotCount = 1;

        if (_dialogueText != null)
            _dialogueText.text = BuildLoadingText(_npcReplyLoadingPrefix, _npcReplyLoadingDotCount);
    }

    /// <summary>
    /// 停止 NPC 回复加载态，并按需清空加载文案。
    /// </summary>
    void StopNpcReplyLoading(bool clearDisplay)
    {
        _isNpcReplyLoading = false;
        _npcReplyLoadingTimer = 0f;
        _npcReplyLoadingDotCount = 0;

        if (clearDisplay && _dialogueText != null)
            _dialogueText.text = "";
        if(clearDisplay && _dialogueText != null)
        {
            _replyHintLabel.text = "";
        }
    }

    /// <summary>
    /// 根据 choices 的实际情况显示真实选项或加载占位。
    /// </summary>
    void ApplySuggestionChoices(List<string> choices, bool startLoadingIfEmpty)
    {
        bool hasChoices = _choiceButtonPrefab != null && _choicesPanel != null && choices != null && choices.Count > 0;
        if (hasChoices)
        {
            StopSuggestionLoading(clearPlaceholders: true);
            RenderChoiceButtons(choices);
            SetChoicesVisible(true);
            return;
        }

        if (startLoadingIfEmpty)
        {
            StartSuggestionLoading();
            return;
        }

        StopSuggestionLoading(clearPlaceholders: true);
        SetChoicesVisible(false);
    }

    /// <summary>
    /// 开始显示快捷回复建议生成中的加载占位。
    /// </summary>
    void StartSuggestionLoading()
    {
        StopSuggestionLoading(clearPlaceholders: true);

        _isSuggestionLoading = true;
        _suggestionLoadingTimer = 0f;
        _suggestionLoadingDotCount = 1;

        if (_choiceButtonPrefab != null && _choicesPanel != null)
        {
            int placeholderCount = Mathf.Max(1, _choiceLoadingPlaceholderCount);
            for (int i = 0; i < placeholderCount; i++)
            {
                var btn = Instantiate(_choiceButtonPrefab, _choicesPanel.transform);
                btn.interactable = false;
                var label = btn.GetComponentInChildren<TMP_Text>();
                if (label != null)
                    _suggestionLoadingLabels.Add(label);
            }
            SetChoicesVisible(true);
        }
        else
        {
            SetChoicesVisible(false);
        }

        UpdateSuggestionLoadingVisual();
    }

    /// <summary>
    /// 停止快捷回复加载态，并按需清除占位按钮。
    /// </summary>
    void StopSuggestionLoading(bool clearPlaceholders)
    {
        _isSuggestionLoading = false;
        _suggestionLoadingTimer = 0f;
        _suggestionLoadingDotCount = 0;

        if (clearPlaceholders)
        {
            ClearChoiceButtons();
            SetChoicesVisible(false);
        }
    }

    /// <summary>
    /// 用真实 choices 渲染快捷回复按钮。
    /// </summary>
    void RenderChoiceButtons(List<string> choices)
    {
        ClearChoiceButtons();

        if (_choicesPanel == null || _choiceButtonPrefab == null || choices == null) return;

        foreach (var choice in choices)
        {
            var btn = Instantiate(_choiceButtonPrefab, _choicesPanel.transform);
            btn.interactable = true;
            var label = btn.GetComponentInChildren<TMP_Text>();
            if (label != null)
                label.text = choice;
            btn.onClick.AddListener(() => OnChoiceClicked(choice));
        }
    }

    /// <summary>
    /// 刷新快捷回复加载占位的动态文案。
    /// </summary>
    void UpdateSuggestionLoadingVisual()
    {
        if (_replyHintLabel != null)
        {
            _replyHintLabel.text =
                $"{BuildLoadingText(_suggestionLoadingPrefix, _suggestionLoadingDotCount)}";
        }

        for (int i = 0; i < _suggestionLoadingLabels.Count; i++)
        {
            var label = _suggestionLoadingLabels[i];
            if (label == null) continue;

            int dotCount = ((_suggestionLoadingDotCount + i - 1) % 3) + 1;
            label.text = BuildLoadingText(_suggestionLoadingPrefix, dotCount);
        }
    }

    /// <summary>
    /// 构造点点点加载文案，例如“思考中...”。
    /// </summary>
    string BuildLoadingText(string prefix, int dotCount)
    {
        return $"{prefix}{new string('.', Mathf.Clamp(dotCount, 1, 3))}";
    }

    /// <summary>
    /// 将加载点数量按 1→2→3→1 的顺序循环。
    /// </summary>
    int NextLoadingDotCount(int currentCount)
    {
        int normalized = Mathf.Clamp(currentCount, 0, 3);
        return normalized >= 3 ? 1 : normalized + 1;
    }

    /// <summary>
    /// 清空输入框中的玩家文本。
    /// </summary>
    void ClearReplyInput()
    {
        if (_replyInputField == null) return;
        _replyInputField.text = "";
    }

    /// <summary>
    /// 聚焦输入框，方便玩家直接输入。
    /// </summary>
    void FocusReplyInput()
    {
        if (_replyInputField == null || EventSystem.current == null) return;

        EventSystem.current.SetSelectedGameObject(_replyInputField.gameObject);
        _replyInputField.ActivateInputField();
        _replyInputField.Select();
    }
}
