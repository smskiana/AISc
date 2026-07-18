using UnityEngine;
using UnityEngine.UI;
using UnityEditor;
using TMPro;
using UnityEngine.EventSystems;

/// <summary>
/// 编辑器工具：一键构建对话 UI 层级和 ChoiceButton 预制体。
/// 菜单: Tools → Build Dialogue UI
/// </summary>
public static class DialogueUIBuilder
{
    [MenuItem("Tools/Build Dialogue UI")]
    public static void Build()
    {
        CreateChoiceButtonPrefab();
        GameObject canvasGo = BuildDialogueCanvas();
        SaveDialogueCanvasPrefab(canvasGo);
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        Debug.Log("[DialogueUIBuilder] 对话 UI 构建完成。");
    }

    static void CreateChoiceButtonPrefab()
    {
        const string prefabPath = "Assets/Prefabs/UI/UI_ChoiceButton.prefab";
        // 确保目录存在
        if (!AssetDatabase.IsValidFolder("Assets/Prefabs/UI"))
            AssetDatabase.CreateFolder("Assets/Prefabs", "UI");

        var existingPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
        GameObject btnGo = existingPrefab != null
            ? PrefabUtility.LoadPrefabContents(prefabPath)
            : new GameObject("btn_choice_st");

        btnGo.name = "btn_choice_st";
        RectTransform btnRt = btnGo.GetComponent<RectTransform>();
        if (btnRt == null) btnRt = btnGo.AddComponent<RectTransform>();
        btnRt.sizeDelta = new Vector2(400f, 50f);

        // Image
        Image img = btnGo.GetComponent<Image>();
        if (img == null) img = btnGo.AddComponent<Image>();
        img.color = new Color(0.96f, 0.9f, 0.83f, 1f); // 奶油色

        // Button
        Button btn = btnGo.GetComponent<Button>();
        if (btn == null) btn = btnGo.AddComponent<Button>();
        ColorBlock cb = btn.colors;
        cb.normalColor = new Color(0.96f, 0.9f, 0.83f);
        cb.highlightedColor = new Color(1f, 0.97f, 0.94f);
        cb.pressedColor = new Color(0.8f, 0.75f, 0.68f);
        cb.selectedColor = new Color(0.96f, 0.9f, 0.83f);
        btn.colors = cb;

        // TMP_Text 子物体
        GameObject labelGo = GetOrCreateChild(btnGo, "txt_choiceLabel_st");
        RectTransform labelRt = labelGo.GetComponent<RectTransform>();
        labelRt.anchorMin = Vector2.zero;
        labelRt.anchorMax = Vector2.one;
        labelRt.sizeDelta = Vector2.zero;

        TMP_Text label = labelGo.GetComponent<TextMeshProUGUI>();
        if (label == null) label = labelGo.AddComponent<TextMeshProUGUI>();
        label.fontSize = 24f;
        label.color = new Color(0.2f, 0.13f, 0.06f);
        label.alignment = TextAlignmentOptions.Center;
        label.text = "选项";
        TmpChineseFontNormalizer.ApplyChineseFont(label);

        // 保存预制体
        if (existingPrefab != null)
        {
            PrefabUtility.SaveAsPrefabAsset(btnGo, prefabPath);
            PrefabUtility.UnloadPrefabContents(btnGo);
            Debug.Log("[DialogueUIBuilder] ChoiceButton 预制体已更新。");
        }
        else
        {
            PrefabUtility.SaveAsPrefabAsset(btnGo, prefabPath);
            Object.DestroyImmediate(btnGo);
            Debug.Log("[DialogueUIBuilder] ChoiceButton 预制体已创建。");
        }
    }

    static GameObject BuildDialogueCanvas()
    {
        EnsureEventSystem();

        // 查找或创建 Canvas
        GameObject canvasGo = GameObject.Find("cvs_dialogue_dy");
        if (canvasGo == null)
        {
            canvasGo = new GameObject("cvs_dialogue_dy");
        }

        // 确保有 Canvas 组件
        Canvas canvas = canvasGo.GetComponent<Canvas>();
        if (canvas == null)
        {
            canvas = canvasGo.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 100;
            canvasGo.AddComponent<CanvasScaler>();
            canvasGo.AddComponent<GraphicRaycaster>();
        }

        // 移除现有的 PortraitDialogueUI（如果存在）
        var existingUI = canvasGo.GetComponent<PortraitDialogueUI>();
        if (existingUI != null)
            Object.DestroyImmediate(existingUI);

        // ── 创建子物体 ──

        // BG_Image（全屏背景）
        GameObject bgGo = GetOrCreateChild(canvasGo, "img_bg_dy");
        Image bgImg = bgGo.GetComponent<Image>();
        if (bgImg == null) bgImg = bgGo.AddComponent<Image>();
        bgImg.color = new Color(0f, 0f, 0f, 0.5f);
        SetFullStretch(bgGo.GetComponent<RectTransform>());

        // PortraitImage（立绘，左下）
        GameObject portraitGo = GetOrCreateChild(canvasGo, "img_portrait_dy");
        Image portraitImg = portraitGo.GetComponent<Image>();
        if (portraitImg == null) portraitImg = portraitGo.AddComponent<Image>();
        portraitImg.color = Color.white;
        portraitImg.preserveAspect = true;
        RectTransform pRt = portraitGo.GetComponent<RectTransform>();
        pRt.anchorMin = new Vector2(0f, 0f);
        pRt.anchorMax = new Vector2(0.35f, 0.85f);
        pRt.anchoredPosition = new Vector2(50f, 30f);
        pRt.sizeDelta = Vector2.zero;

        // PortraitNameLabel（名字标签）
        GameObject pNameGo = GetOrCreateChild(canvasGo, "txt_portraitName_dy");
        TMP_Text pNameText = pNameGo.GetComponent<TextMeshProUGUI>();
        if (pNameText == null) pNameText = pNameGo.AddComponent<TextMeshProUGUI>();
        pNameText.fontSize = 28f;
        pNameText.color = Color.white;
        pNameText.alignment = TextAlignmentOptions.TopLeft;
        TmpChineseFontNormalizer.ApplyChineseFont(pNameText);
        RectTransform pnRt = pNameGo.GetComponent<RectTransform>();
        pnRt.anchorMin = new Vector2(0f, 0.85f);
        pnRt.anchorMax = new Vector2(0.35f, 0.92f);
        pnRt.anchoredPosition = new Vector2(50f, 0f);
        pnRt.sizeDelta = new Vector2(0f, -5f);

        // DialoguePanel（对话框容器）
        GameObject dPanelGo = GetOrCreateChild(canvasGo, "pnl_dialogue_dy");
        RectTransform dpRt = dPanelGo.GetComponent<RectTransform>();
        dpRt.anchorMin = new Vector2(0.1f, 0.02f);
        dpRt.anchorMax = new Vector2(0.9f, 0.28f);
        dpRt.sizeDelta = Vector2.zero;

        // DialogueBG（对话框底图）
        GameObject dBgGo = GetOrCreateChild(dPanelGo, "img_dialogueBg_st");
        Image dBgImg = dBgGo.GetComponent<Image>();
        if (dBgImg == null) dBgImg = dBgGo.AddComponent<Image>();
        dBgImg.color = new Color(0.1f, 0.06f, 0.03f, 0.88f);
        SetFullStretch(dBgGo.GetComponent<RectTransform>());

        // SpeakerNameLabel（说话者名字，对话框左上角）
        GameObject sNameGo = GetOrCreateChild(dPanelGo, "txt_speakerName_dy");
        TMP_Text sNameText = sNameGo.GetComponent<TextMeshProUGUI>();
        if (sNameText == null) sNameText = sNameGo.AddComponent<TextMeshProUGUI>();
        sNameText.fontSize = 22f;
        sNameText.fontStyle = FontStyles.Bold;
        sNameText.color = new Color(1f, 0.85f, 0.6f);
        sNameText.alignment = TextAlignmentOptions.TopLeft;
        TmpChineseFontNormalizer.ApplyChineseFont(sNameText);
        RectTransform snRt = sNameGo.GetComponent<RectTransform>();
        snRt.anchorMin = new Vector2(0f, 1f);
        snRt.anchorMax = new Vector2(1f, 1f);
        snRt.pivot = new Vector2(0f, 1f);
        snRt.anchoredPosition = new Vector2(15f, -10f);
        snRt.sizeDelta = new Vector2(-30f, 30f);

        // DialogueText（对话正文）
        GameObject dTextGo = GetOrCreateChild(dPanelGo, "txt_dialogue_dy");
        TMP_Text dText = dTextGo.GetComponent<TextMeshProUGUI>();
        if (dText == null) dText = dTextGo.AddComponent<TextMeshProUGUI>();
        dText.fontSize = 24f;
        dText.color = Color.white;
        dText.alignment = TextAlignmentOptions.TopLeft;
        dText.lineSpacing = 1.4f;
        TmpChineseFontNormalizer.ApplyChineseFont(dText);
        RectTransform dtRt = dTextGo.GetComponent<RectTransform>();
        dtRt.anchorMin = Vector2.zero;
        dtRt.anchorMax = Vector2.one;
        dtRt.anchoredPosition = new Vector2(15f, 10f);
        dtRt.sizeDelta = new Vector2(-30f, -50f);

        // ChoicesPanel（选项容器，初始隐藏）
        GameObject choicesGo = GetOrCreateChild(canvasGo, "pnl_choices_dy");
        choicesGo.SetActive(false);
        RectTransform chRt = choicesGo.GetComponent<RectTransform>();
        chRt.anchorMin = new Vector2(0.5f, 0.3f);
        chRt.anchorMax = new Vector2(0.95f, 0.8f);
        chRt.sizeDelta = Vector2.zero;
        // VerticalLayoutGroup
        VerticalLayoutGroup vlg = choicesGo.GetComponent<VerticalLayoutGroup>();
        if (vlg == null) vlg = choicesGo.AddComponent<VerticalLayoutGroup>();
        vlg.spacing = 8f;
        vlg.padding = new RectOffset(10, 10, 10, 10);
        vlg.childAlignment = TextAnchor.UpperCenter;
        vlg.childControlWidth = true;
        vlg.childControlHeight = true;
        // ContentSizeFitter
        ContentSizeFitter csf = choicesGo.GetComponent<ContentSizeFitter>();
        if (csf == null) csf = choicesGo.AddComponent<ContentSizeFitter>();
        csf.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

        // ReplyPanel（玩家回复区，初始隐藏）
        GameObject replyPanelGo = GetOrCreateChild(canvasGo, "pnl_reply_dy");
        replyPanelGo.SetActive(false);
        Image replyBg = replyPanelGo.GetComponent<Image>();
        if (replyBg == null) replyBg = replyPanelGo.AddComponent<Image>();
        replyBg.color = new Color(0.16f, 0.1f, 0.06f, 0.92f);
        RectTransform rpRt = replyPanelGo.GetComponent<RectTransform>();
        rpRt.anchorMin = new Vector2(0.5f, 0.3f);
        rpRt.anchorMax = new Vector2(0.95f, 0.52f);
        rpRt.sizeDelta = Vector2.zero;
        rpRt.anchoredPosition = Vector2.zero;

        // ReplyHintLabel
        GameObject replyHintGo = GetOrCreateChild(replyPanelGo, "txt_replyHint_dy");
        TMP_Text replyHintText = replyHintGo.GetComponent<TextMeshProUGUI>();
        if (replyHintText == null) replyHintText = replyHintGo.AddComponent<TextMeshProUGUI>();
        replyHintText.fontSize = 18f;
        replyHintText.color = new Color(1f, 0.9f, 0.75f, 0.9f);
        replyHintText.alignment = TextAlignmentOptions.Left;
        replyHintText.text = "可点选建议，也可自由输入；Enter 发送，Esc 结束对话";
        TmpChineseFontNormalizer.ApplyChineseFont(replyHintText);
        RectTransform rhRt = replyHintGo.GetComponent<RectTransform>();
        rhRt.anchorMin = new Vector2(0.05f, 0.76f);
        rhRt.anchorMax = new Vector2(0.95f, 0.96f);
        rhRt.sizeDelta = Vector2.zero;
        rhRt.anchoredPosition = Vector2.zero;

        // ReplyInputField
        GameObject replyInputGo = GetOrCreateChild(replyPanelGo, "inp_reply_dy");
        Image replyInputBg = replyInputGo.GetComponent<Image>();
        if (replyInputBg == null) replyInputBg = replyInputGo.AddComponent<Image>();
        replyInputBg.color = new Color(0.96f, 0.92f, 0.86f, 1f);
        TMP_InputField inputField = replyInputGo.GetComponent<TMP_InputField>();
        if (inputField == null) inputField = replyInputGo.AddComponent<TMP_InputField>();
        RectTransform riRt = replyInputGo.GetComponent<RectTransform>();
        riRt.anchorMin = new Vector2(0.05f, 0.34f);
        riRt.anchorMax = new Vector2(0.95f, 0.68f);
        riRt.sizeDelta = Vector2.zero;
        riRt.anchoredPosition = Vector2.zero;

        GameObject textAreaGo = GetOrCreateChild(replyInputGo, "go_textArea_st");
        RectTransform taRt = textAreaGo.GetComponent<RectTransform>();
        taRt.anchorMin = Vector2.zero;
        taRt.anchorMax = Vector2.one;
        taRt.offsetMin = new Vector2(16f, 8f);
        taRt.offsetMax = new Vector2(-16f, -8f);
        RectMask2D mask = textAreaGo.GetComponent<RectMask2D>();
        if (mask == null) mask = textAreaGo.AddComponent<RectMask2D>();

        GameObject placeholderGo = GetOrCreateChild(textAreaGo, "txt_placeholder_st");
        TMP_Text placeholderText = placeholderGo.GetComponent<TextMeshProUGUI>();
        if (placeholderText == null) placeholderText = placeholderGo.AddComponent<TextMeshProUGUI>();
        placeholderText.fontSize = 22f;
        placeholderText.color = new Color(0.34f, 0.26f, 0.18f, 0.45f);
        placeholderText.alignment = TextAlignmentOptions.Left;
        placeholderText.text = "和对方说点什么……";
        TmpChineseFontNormalizer.ApplyChineseFont(placeholderText);
        RectTransform phRt = placeholderGo.GetComponent<RectTransform>();
        phRt.anchorMin = Vector2.zero;
        phRt.anchorMax = Vector2.one;
        phRt.sizeDelta = Vector2.zero;
        phRt.anchoredPosition = Vector2.zero;

        GameObject inputTextGo = GetOrCreateChild(textAreaGo, "txt_input_dy");
        TMP_Text inputText = inputTextGo.GetComponent<TextMeshProUGUI>();
        if (inputText == null) inputText = inputTextGo.AddComponent<TextMeshProUGUI>();
        inputText.fontSize = 22f;
        inputText.color = new Color(0.2f, 0.13f, 0.06f, 1f);
        inputText.alignment = TextAlignmentOptions.Left;
        TmpChineseFontNormalizer.ApplyChineseFont(inputText);
        RectTransform itRt = inputTextGo.GetComponent<RectTransform>();
        itRt.anchorMin = Vector2.zero;
        itRt.anchorMax = Vector2.one;
        itRt.sizeDelta = Vector2.zero;
        itRt.anchoredPosition = Vector2.zero;

        inputField.textViewport = taRt;
        inputField.textComponent = (TextMeshProUGUI)inputText;
        inputField.placeholder = placeholderText;
        inputField.lineType = TMP_InputField.LineType.SingleLine;
        inputField.characterLimit = 80;

        // SendButton
        Button sendButton = EnsureTextButton(
            replyPanelGo,
            "btn_send_st",
            "txt_sendLabel_st",
            "发送",
            new Vector2(0.52f, 0.08f),
            new Vector2(0.72f, 0.28f),
            new Color(0.78f, 0.54f, 0.35f, 1f));

        // EndDialogueButton
        Button endButton = EnsureTextButton(
            replyPanelGo,
            "btn_endDialogue_st",
            "txt_endDialogueLabel_st",
            "结束对话",
            new Vector2(0.75f, 0.08f),
            new Vector2(0.95f, 0.28f),
            new Color(0.42f, 0.28f, 0.2f, 1f));

        // ── 添加 PortraitDialogueUI 组件 ──
        PortraitDialogueUI dialogueUI = canvasGo.AddComponent<PortraitDialogueUI>();

        // ── 连线 SerializedField 引用 ──
        SerializedObject so = new SerializedObject(dialogueUI);

        // 数据引用
        var locationBgData = AssetDatabase.LoadAssetAtPath<LocationBackgroundData>("Assets/Data/LocationBackgrounds.asset");
        SetSerializedField(so, "_backgroundData", locationBgData);

        // PortraitData 数组
        var sakura = AssetDatabase.LoadAssetAtPath<NpcPortraitData>("Assets/Data/lihun/Portrait_sakura.asset");
        var chihaya = AssetDatabase.LoadAssetAtPath<NpcPortraitData>("Assets/Data/lihun/Portrait_chihaya.asset");
        var kazuha = AssetDatabase.LoadAssetAtPath<NpcPortraitData>("Assets/Data/lihun/Portrait_kazuha.asset");
        var tatsunosuke = AssetDatabase.LoadAssetAtPath<NpcPortraitData>("Assets/Data/lihun/Portrait_tatsunosuke.asset");
        var kujo = AssetDatabase.LoadAssetAtPath<NpcPortraitData>("Assets/Data/lihun/Portrait_kujo.asset");

        SerializedProperty portraitsProp = so.FindProperty("_portraitDatas");
        if (portraitsProp != null)
        {
            portraitsProp.arraySize = 5;
            portraitsProp.GetArrayElementAtIndex(0).objectReferenceValue = sakura;
            portraitsProp.GetArrayElementAtIndex(1).objectReferenceValue = chihaya;
            portraitsProp.GetArrayElementAtIndex(2).objectReferenceValue = kazuha;
            portraitsProp.GetArrayElementAtIndex(3).objectReferenceValue = tatsunosuke;
            portraitsProp.GetArrayElementAtIndex(4).objectReferenceValue = kujo;
        }

        // UI 引用
        SetSerializedField(so, "_bgImage", bgImg);
        SetSerializedField(so, "_portraitImage", portraitImg);
        SetSerializedField(so, "_portraitNameLabel", pNameText);
        SetSerializedField(so, "_dialoguePanel", dPanelGo);
        SetSerializedField(so, "_dialogueText", dText);
        SetSerializedField(so, "_speakerNameLabel", sNameText);
        SetSerializedField(so, "_choicesPanel", choicesGo);
        SetSerializedField(so, "_replyPanel", replyPanelGo);
        SetSerializedField(so, "_replyHintLabel", replyHintText);
        SetSerializedField(so, "_replyInputField", inputField);
        SetSerializedField(so, "_sendButton", sendButton);
        SetSerializedField(so, "_endDialogueButton", endButton);

        // ChoiceButton 预制体
        var choicePrefab = AssetDatabase.LoadAssetAtPath<Button>("Assets/Prefabs/UI/UI_ChoiceButton.prefab");
        SetSerializedField(so, "_choiceButtonPrefab", choicePrefab);

        so.ApplyModifiedPropertiesWithoutUndo();

        // ── 连线 GameManager._dialogueUI ──
        var gm = Object.FindObjectOfType<GameManager>();
        if (gm != null)
        {
            SerializedObject gmSo = new SerializedObject(gm);
            SetSerializedField(gmSo, "_dialogueUI", dialogueUI);
            gmSo.ApplyModifiedPropertiesWithoutUndo();
            Debug.Log("[DialogueUIBuilder] GameManager._dialogueUI 已连线。");
        }
        else
        {
            Debug.LogWarning("[DialogueUIBuilder] 场景中未找到 GameManager！");
        }

        Debug.Log("[DialogueUIBuilder] DialogueCanvas 构建完成。");
        return canvasGo;
    }

    static GameObject GetOrCreateChild(GameObject parent, string name)
    {
        Transform existing = parent.transform.Find(name);
        if (existing != null)
            return existing.gameObject;

        GameObject child = new GameObject(name);
        child.transform.SetParent(parent.transform, false);
        child.AddComponent<RectTransform>();
        return child;
    }

    static void SetFullStretch(RectTransform rt)
    {
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.anchoredPosition = Vector2.zero;
        rt.sizeDelta = Vector2.zero;
    }

    static void SetSerializedField(SerializedObject so, string fieldName, Object value)
    {
        SerializedProperty prop = so.FindProperty(fieldName);
        if (prop != null)
            prop.objectReferenceValue = value;
        else
            Debug.LogWarning($"[DialogueUIBuilder] 找不到字段: {fieldName}");
    }

    static void EnsureEventSystem()
    {
        if (Object.FindObjectOfType<EventSystem>() != null) return;

        GameObject eventSystemGo = new GameObject("event_system_st");
        eventSystemGo.AddComponent<EventSystem>();
        eventSystemGo.AddComponent<StandaloneInputModule>();
        Debug.Log("[DialogueUIBuilder] 已创建 EventSystem。");
    }

    static Button EnsureTextButton(GameObject parent, string name, string labelObjectName, string label, Vector2 anchorMin, Vector2 anchorMax, Color backgroundColor)
    {
        GameObject buttonGo = GetOrCreateChild(parent, name);
        Image image = buttonGo.GetComponent<Image>();
        if (image == null) image = buttonGo.AddComponent<Image>();
        image.color = backgroundColor;

        Button button = buttonGo.GetComponent<Button>();
        if (button == null) button = buttonGo.AddComponent<Button>();

        ColorBlock cb = button.colors;
        cb.normalColor = backgroundColor;
        cb.highlightedColor = backgroundColor * 1.1f;
        cb.pressedColor = backgroundColor * 0.9f;
        cb.selectedColor = backgroundColor;
        button.colors = cb;

        RectTransform rt = buttonGo.GetComponent<RectTransform>();
        rt.anchorMin = anchorMin;
        rt.anchorMax = anchorMax;
        rt.sizeDelta = Vector2.zero;
        rt.anchoredPosition = Vector2.zero;

        GameObject labelGo = GetOrCreateChild(buttonGo, labelObjectName);
        TMP_Text labelText = labelGo.GetComponent<TextMeshProUGUI>();
        if (labelText == null) labelText = labelGo.AddComponent<TextMeshProUGUI>();
        labelText.fontSize = 20f;
        labelText.color = Color.white;
        labelText.alignment = TextAlignmentOptions.Center;
        labelText.text = label;
        TmpChineseFontNormalizer.ApplyChineseFont(labelText);

        RectTransform labelRt = labelGo.GetComponent<RectTransform>();
        labelRt.anchorMin = Vector2.zero;
        labelRt.anchorMax = Vector2.one;
        labelRt.sizeDelta = Vector2.zero;
        labelRt.anchoredPosition = Vector2.zero;

        return button;
    }

    static void SaveDialogueCanvasPrefab(GameObject canvasGo)
    {
        if (canvasGo == null) return;

        if (!AssetDatabase.IsValidFolder("Assets/Prefabs/UI"))
            AssetDatabase.CreateFolder("Assets/Prefabs", "UI");

        const string prefabPath = "Assets/Prefabs/UI/UI_DialogueCanvas.prefab";
        PrefabUtility.SaveAsPrefabAssetAndConnect(canvasGo, prefabPath, InteractionMode.AutomatedAction);
        Debug.Log("[DialogueUIBuilder] DialogueCanvas 预制体已更新。");
    }
}
