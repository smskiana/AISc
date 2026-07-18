using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

/// <summary>
/// 编辑器工具：一键构建开始界面层级、按钮预制体和控制器连线。
/// 菜单: Tools → Build Start Menu
/// </summary>
public static class StartMenuBuilder
{
    private const string SaveButtonPrefabPath = "Assets/Prefabs/UI/UI_StartMenuSaveButton.prefab";
    private const string CanvasPrefabPath = "Assets/Prefabs/UI/UI_StartMenuCanvas.prefab";
    private const string BackgroundSpritePath = "Assets/Art/Generated/PixelScenes/street_arcade_pixel_v1.png";

    [MenuItem("Tools/Build Start Menu")]
    public static void Build()
    {
        EnsureEventSystem();
        StartMenuSaveButtonView saveButtonPrefab = BuildSaveButtonPrefab();
        StartMenuView startMenuView = BuildStartMenuCanvas(saveButtonPrefab);
        BuildStartMenuController(startMenuView);
        SaveStartMenuCanvasPrefab(startMenuView != null ? startMenuView.gameObject : null);
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        Debug.Log("[StartMenuBuilder] 开始界面构建完成。");
    }

    private static StartMenuSaveButtonView BuildSaveButtonPrefab()
    {
        EnsureUiPrefabFolder();

        GameObject buttonGo = new GameObject("btn_loadSlot_st");
        RectTransform buttonRt = buttonGo.AddComponent<RectTransform>();
        buttonRt.sizeDelta = new Vector2(760f, 54f);

        Image buttonImage = buttonGo.AddComponent<Image>();
        buttonImage.color = new Color(0.18f, 0.14f, 0.09f, 0.94f);

        Button button = buttonGo.AddComponent<Button>();
        ColorBlock colors = button.colors;
        colors.normalColor = buttonImage.color;
        colors.highlightedColor = buttonImage.color * 1.08f;
        colors.pressedColor = buttonImage.color * 0.88f;
        colors.selectedColor = buttonImage.color;
        button.colors = colors;

        GameObject labelGo = new GameObject("txt_buttonLabel_dy");
        labelGo.transform.SetParent(buttonGo.transform, false);
        RectTransform labelRt = labelGo.AddComponent<RectTransform>();
        SetFullStretch(labelRt);

        TextMeshProUGUI label = labelGo.AddComponent<TextMeshProUGUI>();
        label.fontSize = 24f;
        label.color = Color.white;
        label.alignment = TextAlignmentOptions.Center;
        label.text = "载入 slot_1";
        TmpChineseFontNormalizer.ApplyChineseFont(label);

        buttonGo.AddComponent<StartMenuSaveButtonView>();

        PrefabUtility.SaveAsPrefabAsset(buttonGo, SaveButtonPrefabPath);
        Object.DestroyImmediate(buttonGo);
        return AssetDatabase.LoadAssetAtPath<StartMenuSaveButtonView>(SaveButtonPrefabPath);
    }

    private static StartMenuView BuildStartMenuCanvas(StartMenuSaveButtonView saveButtonPrefab)
    {
        GameObject canvasGo = GameObject.Find("cvs_startMenu_dy");
        if (canvasGo == null)
            canvasGo = new GameObject("cvs_startMenu_dy");

        RectTransform canvasRt = EnsureRectTransform(canvasGo);
        Canvas canvas = canvasGo.GetComponent<Canvas>();
        if (canvas == null)
            canvas = canvasGo.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 300;

        CanvasScaler scaler = canvasGo.GetComponent<CanvasScaler>();
        if (scaler == null)
            scaler = canvasGo.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920f, 1080f);
        scaler.screenMatchMode = CanvasScaler.ScreenMatchMode.MatchWidthOrHeight;
        scaler.matchWidthOrHeight = 0.5f;

        if (canvasGo.GetComponent<GraphicRaycaster>() == null)
            canvasGo.AddComponent<GraphicRaycaster>();

        SetFullStretch(canvasRt);

        GameObject bgGo = GetOrCreateChild(canvasGo, "img_startBackground_dy");
        Image bgImage = EnsureImage(bgGo, Color.white);
        bgImage.sprite = AssetDatabase.LoadAssetAtPath<Sprite>(BackgroundSpritePath);
        bgImage.preserveAspect = false;
        SetFullStretch(bgGo.GetComponent<RectTransform>());

        GameObject veilGo = GetOrCreateChild(canvasGo, "img_startVeil_dy");
        Image veilImage = EnsureImage(veilGo, new Color(0.04f, 0.03f, 0.02f, 0.56f));
        SetFullStretch(veilGo.GetComponent<RectTransform>());

        GameObject panelGo = GetOrCreateChild(canvasGo, "pnl_startMenu_dy");
        RectTransform panelRt = panelGo.GetComponent<RectTransform>();
        SetAnchors(panelRt, new Vector2(0.18f, 0.12f), new Vector2(0.82f, 0.88f));
        Image panelImage = EnsureImage(panelGo, new Color(0.08f, 0.06f, 0.04f, 0.88f));

        TextMeshProUGUI titleLabel = EnsureLabel(
            panelGo,
            "txt_title_dy",
            "樱桥通",
            54f,
            FontStyles.Bold,
            new Color(1f, 0.92f, 0.78f, 1f),
            new Vector2(0.08f, 0.82f),
            new Vector2(0.92f, 0.95f),
            TextAlignmentOptions.Center);

        TextMeshProUGUI subtitleLabel = EnsureLabel(
            panelGo,
            "txt_subtitle_dy",
            "登录、启动后端并选择存档",
            24f,
            FontStyles.Normal,
            new Color(0.96f, 0.88f, 0.74f, 0.95f),
            new Vector2(0.08f, 0.76f),
            new Vector2(0.92f, 0.83f),
            TextAlignmentOptions.Center);

        TextMeshProUGUI statusLabel = EnsureLabel(
            panelGo,
            "txt_status_dy",
            "正在初始化开始界面...",
            22f,
            FontStyles.Normal,
            Color.white,
            new Vector2(0.08f, 0.66f),
            new Vector2(0.92f, 0.74f),
            TextAlignmentOptions.Center);

        EnsureLabel(
            panelGo,
            "txt_nameLabel_st",
            "本地玩家名",
            22f,
            FontStyles.Bold,
            new Color(1f, 0.9f, 0.76f, 1f),
            new Vector2(0.1f, 0.57f),
            new Vector2(0.32f, 0.63f),
            TextAlignmentOptions.MidlineLeft);

        TMP_InputField nameInputField = EnsureInputField(
            panelGo,
            "inp_playerName_dy",
            "输入本地显示名",
            new Vector2(0.1f, 0.49f),
            new Vector2(0.64f, 0.57f));

        Button loginButton = EnsureTextButton(
            panelGo,
            "btn_login_st",
            "txt_buttonLabel_st",
            "记录名字",
            new Vector2(0.68f, 0.49f),
            new Vector2(0.9f, 0.57f),
            new Color(0.72f, 0.48f, 0.28f, 1f),
            22f);

        Button retryBackendButton = EnsureTextButton(
            panelGo,
            "btn_startBackend_st",
            "txt_buttonLabel_st",
            "启动后端并连接",
            new Vector2(0.1f, 0.39f),
            new Vector2(0.42f, 0.46f),
            new Color(0.34f, 0.24f, 0.14f, 1f),
            21f);

        Button refreshSavesButton = EnsureTextButton(
            panelGo,
            "btn_refreshSaves_st",
            "txt_buttonLabel_st",
            "刷新存档",
            new Vector2(0.45f, 0.39f),
            new Vector2(0.64f, 0.46f),
            new Color(0.24f, 0.19f, 0.12f, 1f),
            21f);

        Button newGameButton = EnsureTextButton(
            panelGo,
            "btn_newGame_st",
            "txt_buttonLabel_st",
            "开始新游戏",
            new Vector2(0.68f, 0.36f),
            new Vector2(0.9f, 0.46f),
            new Color(0.8f, 0.56f, 0.34f, 1f),
            24f);

        TextMeshProUGUI saveListTitle = EnsureLabel(
            panelGo,
            "txt_saveListTitle_dy",
            "存档列表",
            24f,
            FontStyles.Bold,
            new Color(1f, 0.9f, 0.76f, 1f),
            new Vector2(0.1f, 0.28f),
            new Vector2(0.9f, 0.34f),
            TextAlignmentOptions.MidlineLeft);

        GameObject savePanelGo = GetOrCreateChild(panelGo, "pnl_saveList_dy");
        RectTransform savePanelRt = savePanelGo.GetComponent<RectTransform>();
        SetAnchors(savePanelRt, new Vector2(0.08f, 0.08f), new Vector2(0.92f, 0.27f));
        Image savePanelImage = EnsureImage(savePanelGo, new Color(0.14f, 0.11f, 0.08f, 0.92f));

        GameObject saveContentGo = GetOrCreateChild(savePanelGo, "go_saveListContent_dy");
        RectTransform saveContentRt = saveContentGo.GetComponent<RectTransform>();
        SetAnchors(saveContentRt, Vector2.zero, Vector2.one, new Vector2(16f, 16f), new Vector2(-16f, -16f));
        VerticalLayoutGroup layoutGroup = saveContentGo.GetComponent<VerticalLayoutGroup>();
        if (layoutGroup == null)
            layoutGroup = saveContentGo.AddComponent<VerticalLayoutGroup>();
        layoutGroup.spacing = 12f;
        layoutGroup.childControlWidth = true;
        layoutGroup.childControlHeight = true;
        layoutGroup.childForceExpandHeight = false;
        layoutGroup.childForceExpandWidth = true;
        layoutGroup.childAlignment = TextAnchor.UpperCenter;

        GameObject saveEmptyGo = GetOrCreateChild(savePanelGo, "txt_saveListEmpty_dy");
        RectTransform saveEmptyRt = saveEmptyGo.GetComponent<RectTransform>();
        SetAnchors(saveEmptyRt, Vector2.zero, Vector2.one);
        TextMeshProUGUI saveListEmptyLabel = EnsureTmp(saveEmptyGo);
        saveListEmptyLabel.fontSize = 20f;
        saveListEmptyLabel.fontStyle = FontStyles.Italic;
        saveListEmptyLabel.color = new Color(0.95f, 0.88f, 0.78f, 0.82f);
        saveListEmptyLabel.alignment = TextAlignmentOptions.Center;
        saveListEmptyLabel.text = "连接后将显示存档列表。";

        StartMenuView startMenuView = canvasGo.GetComponent<StartMenuView>();
        if (startMenuView == null)
            startMenuView = canvasGo.AddComponent<StartMenuView>();

        SerializedObject viewSo = new SerializedObject(startMenuView);
        SetSerializedField(viewSo, "_canvas", canvas);
        SetSerializedField(viewSo, "_statusLabel", statusLabel);
        SetSerializedField(viewSo, "_saveListEmptyLabel", saveListEmptyLabel);
        SetSerializedField(viewSo, "_nameInputField", nameInputField);
        SetSerializedField(viewSo, "_loginButton", loginButton);
        SetSerializedField(viewSo, "_newGameButton", newGameButton);
        SetSerializedField(viewSo, "_refreshSavesButton", refreshSavesButton);
        SetSerializedField(viewSo, "_retryBackendButton", retryBackendButton);
        SetSerializedField(viewSo, "_saveListContentRoot", saveContentGo.transform);
        SetSerializedField(viewSo, "_saveButtonPrefab", saveButtonPrefab);
        viewSo.ApplyModifiedPropertiesWithoutUndo();

        titleLabel.name = "txt_title_dy";
        subtitleLabel.name = "txt_subtitle_dy";
        panelImage.name = "pnl_startMenu_dy";
        veilImage.name = "img_startVeil_dy";
        bgImage.name = "img_startBackground_dy";
        saveListTitle.name = "txt_saveListTitle_dy";
        savePanelImage.name = "pnl_saveList_dy";

        return startMenuView;
    }

    private static void BuildStartMenuController(StartMenuView view)
    {
        GameObject controllerGo = GameObject.Find("go_startMenuController_dy");
        if (controllerGo == null)
            controllerGo = new GameObject("go_startMenuController_dy");

        StartMenuController controller = controllerGo.GetComponent<StartMenuController>();
        if (controller == null)
            controller = controllerGo.AddComponent<StartMenuController>();

        SerializedObject controllerSo = new SerializedObject(controller);
        SetSerializedField(controllerSo, "_view", view);
        controllerSo.ApplyModifiedPropertiesWithoutUndo();
    }

    private static void SaveStartMenuCanvasPrefab(GameObject canvasGo)
    {
        if (canvasGo == null) return;
        EnsureUiPrefabFolder();
        PrefabUtility.SaveAsPrefabAssetAndConnect(canvasGo, CanvasPrefabPath, InteractionMode.AutomatedAction);
    }

    private static void EnsureUiPrefabFolder()
    {
        if (!AssetDatabase.IsValidFolder("Assets/Prefabs/UI"))
            AssetDatabase.CreateFolder("Assets/Prefabs", "UI");
    }

    private static void EnsureEventSystem()
    {
        if (Object.FindObjectOfType<EventSystem>() != null) return;

        GameObject eventSystemGo = new GameObject("eventSystem_st");
        eventSystemGo.AddComponent<EventSystem>();
        eventSystemGo.AddComponent<StandaloneInputModule>();
    }

    private static GameObject GetOrCreateChild(GameObject parent, string name)
    {
        Transform existing = parent.transform.Find(name);
        if (existing != null)
            return existing.gameObject;

        GameObject child = new GameObject(name);
        child.transform.SetParent(parent.transform, false);
        child.AddComponent<RectTransform>();
        return child;
    }

    private static RectTransform EnsureRectTransform(GameObject gameObject)
    {
        RectTransform rectTransform = gameObject.GetComponent<RectTransform>();
        if (rectTransform == null)
            rectTransform = gameObject.AddComponent<RectTransform>();
        return rectTransform;
    }

    private static Image EnsureImage(GameObject gameObject, Color color)
    {
        Image image = gameObject.GetComponent<Image>();
        if (image == null)
            image = gameObject.AddComponent<Image>();
        image.color = color;
        return image;
    }

    private static TextMeshProUGUI EnsureTmp(GameObject gameObject)
    {
        TextMeshProUGUI text = gameObject.GetComponent<TextMeshProUGUI>();
        if (text == null)
            text = gameObject.AddComponent<TextMeshProUGUI>();
        TmpChineseFontNormalizer.ApplyChineseFont(text);
        return text;
    }

    private static TextMeshProUGUI EnsureLabel(
        GameObject parent,
        string name,
        string text,
        float fontSize,
        FontStyles fontStyle,
        Color color,
        Vector2 anchorMin,
        Vector2 anchorMax,
        TextAlignmentOptions alignment)
    {
        GameObject labelGo = GetOrCreateChild(parent, name);
        RectTransform labelRt = labelGo.GetComponent<RectTransform>();
        SetAnchors(labelRt, anchorMin, anchorMax);

        TextMeshProUGUI label = EnsureTmp(labelGo);
        label.text = text;
        label.fontSize = fontSize;
        label.fontStyle = fontStyle;
        label.color = color;
        label.alignment = alignment;
        return label;
    }

    private static TMP_InputField EnsureInputField(GameObject parent, string name, string placeholder, Vector2 anchorMin, Vector2 anchorMax)
    {
        GameObject inputGo = GetOrCreateChild(parent, name);
        RectTransform inputRt = inputGo.GetComponent<RectTransform>();
        SetAnchors(inputRt, anchorMin, anchorMax);

        Image inputBg = EnsureImage(inputGo, new Color(0.96f, 0.93f, 0.88f, 1f));
        TMP_InputField inputField = inputGo.GetComponent<TMP_InputField>();
        if (inputField == null)
            inputField = inputGo.AddComponent<TMP_InputField>();

        GameObject textAreaGo = GetOrCreateChild(inputGo, "go_textArea_st");
        RectTransform textAreaRt = textAreaGo.GetComponent<RectTransform>();
        SetAnchors(textAreaRt, Vector2.zero, Vector2.one, new Vector2(16f, 8f), new Vector2(-16f, -8f));
        if (textAreaGo.GetComponent<RectMask2D>() == null)
            textAreaGo.AddComponent<RectMask2D>();

        GameObject placeholderGo = GetOrCreateChild(textAreaGo, "txt_placeholder_st");
        RectTransform placeholderRt = placeholderGo.GetComponent<RectTransform>();
        SetAnchors(placeholderRt, Vector2.zero, Vector2.one);
        TextMeshProUGUI placeholderText = EnsureTmp(placeholderGo);
        placeholderText.text = placeholder;
        placeholderText.fontSize = 22f;
        placeholderText.fontStyle = FontStyles.Italic;
        placeholderText.color = new Color(0.34f, 0.26f, 0.18f, 0.45f);
        placeholderText.alignment = TextAlignmentOptions.MidlineLeft;

        GameObject inputTextGo = GetOrCreateChild(textAreaGo, "txt_input_dy");
        RectTransform inputTextRt = inputTextGo.GetComponent<RectTransform>();
        SetAnchors(inputTextRt, Vector2.zero, Vector2.one);
        TextMeshProUGUI inputText = EnsureTmp(inputTextGo);
        inputText.text = string.Empty;
        inputText.fontSize = 22f;
        inputText.color = new Color(0.17f, 0.11f, 0.06f, 1f);
        inputText.alignment = TextAlignmentOptions.MidlineLeft;

        inputField.textViewport = textAreaRt;
        inputField.textComponent = inputText;
        inputField.placeholder = placeholderText;
        inputField.lineType = TMP_InputField.LineType.SingleLine;
        inputField.characterLimit = 24;
        return inputField;
    }

    private static Button EnsureTextButton(
        GameObject parent,
        string name,
        string labelObjectName,
        string label,
        Vector2 anchorMin,
        Vector2 anchorMax,
        Color backgroundColor,
        float fontSize)
    {
        GameObject buttonGo = GetOrCreateChild(parent, name);
        RectTransform buttonRt = buttonGo.GetComponent<RectTransform>();
        SetAnchors(buttonRt, anchorMin, anchorMax);

        Image image = EnsureImage(buttonGo, backgroundColor);
        Button button = buttonGo.GetComponent<Button>();
        if (button == null)
            button = buttonGo.AddComponent<Button>();

        ColorBlock colors = button.colors;
        colors.normalColor = backgroundColor;
        colors.highlightedColor = backgroundColor * 1.08f;
        colors.pressedColor = backgroundColor * 0.88f;
        colors.selectedColor = backgroundColor;
        button.colors = colors;

        GameObject labelGo = GetOrCreateChild(buttonGo, labelObjectName);
        RectTransform labelRt = labelGo.GetComponent<RectTransform>();
        SetAnchors(labelRt, Vector2.zero, Vector2.one);
        TextMeshProUGUI labelText = EnsureTmp(labelGo);
        labelText.fontSize = fontSize;
        labelText.fontStyle = FontStyles.Bold;
        labelText.color = Color.white;
        labelText.alignment = TextAlignmentOptions.Center;
        labelText.text = label;
        return button;
    }

    private static void SetSerializedField(SerializedObject serializedObject, string fieldName, Object value)
    {
        SerializedProperty property = serializedObject.FindProperty(fieldName);
        if (property == null)
        {
            Debug.LogWarning($"[StartMenuBuilder] 找不到字段: {fieldName}");
            return;
        }

        property.objectReferenceValue = value;
    }

    private static void SetFullStretch(RectTransform rectTransform)
    {
        rectTransform.anchorMin = Vector2.zero;
        rectTransform.anchorMax = Vector2.one;
        rectTransform.offsetMin = Vector2.zero;
        rectTransform.offsetMax = Vector2.zero;
        rectTransform.anchoredPosition = Vector2.zero;
        rectTransform.sizeDelta = Vector2.zero;
    }

    private static void SetAnchors(
        RectTransform rectTransform,
        Vector2 anchorMin,
        Vector2 anchorMax,
        Vector2? offsetMin = null,
        Vector2? offsetMax = null)
    {
        rectTransform.anchorMin = anchorMin;
        rectTransform.anchorMax = anchorMax;
        rectTransform.offsetMin = offsetMin ?? Vector2.zero;
        rectTransform.offsetMax = offsetMax ?? Vector2.zero;
        rectTransform.anchoredPosition = Vector2.zero;
    }
}
