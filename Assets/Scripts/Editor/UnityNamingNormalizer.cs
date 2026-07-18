using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

/// <summary>
/// 编辑器工具：按项目三段 tag 规则规范化现有 scene 与 prefab 命名。
/// </summary>
public static class UnityNamingNormalizer
{
    private const string OldScenePath = "Assets/Scenes/SampleScene.scene";
    private const string NewScenePath = "Assets/Scenes/Town_Main.scene";

    private static readonly (string OldPath, string NewPath)[] AssetRenames =
    {
        ("Assets/Prefabs/UI/DialogueCanvas.prefab", "Assets/Prefabs/UI/UI_DialogueCanvas.prefab"),
        ("Assets/Prefabs/UI/ChoiceButton.prefab", "Assets/Prefabs/UI/UI_ChoiceButton.prefab"),
        ("Assets/Prefabs/Player/Player.prefab", "Assets/Prefabs/Player/Player_Main.prefab"),
        ("Assets/Prefabs/NPCs/01_Sakura.prefab", "Assets/Prefabs/NPCs/Npc_Sakura.prefab"),
        ("Assets/Prefabs/NPCs/02_Chihaya.prefab", "Assets/Prefabs/NPCs/Npc_Chihaya.prefab"),
        ("Assets/Prefabs/NPCs/03_Kazuha.prefab", "Assets/Prefabs/NPCs/Npc_Kazuha.prefab"),
        ("Assets/Prefabs/NPCs/04_Tatsunosuke.prefab", "Assets/Prefabs/NPCs/Npc_Tatsunosuke.prefab"),
        ("Assets/Prefabs/NPCs/05_Kujo.prefab", "Assets/Prefabs/NPCs/Npc_Kujo.prefab"),
    };

    private static readonly HashSet<string> ComponentTags = new()
    {
        "btn",
        "pnl",
        "txt",
        "img",
        "inp",
        "spr",
        "cvs",
        "anc",
        "go",
    };

    private static readonly Dictionary<string, string> SceneRenames = new()
    {
        {"main_camera_st", "mainCamera_st"},
        {"game_manager_st", "gameManager_st"},
        {"go_legacy_scene_root_st", "go_legacySceneRoot_st"},
        {"go_legacy_grid_map_st", "go_legacyGridMap_st"},
        {"go_pixel_scene_root_st", "go_pixelSceneRoot_st"},
        {"go_scene_anchors_st", "go_sceneAnchors_st"},
        {"event_system_st", "eventSystem_st"},
        {"npc_spawner_legacy_st", "go_npcSpawnerLegacy_st"},
        {"npc_bubble_manager_legacy_st", "go_npcBubbleManagerLegacy_st"},
        {"legacy_event_system_st", "go_legacyEventSystem_st"},
        {"txt_speaker_name_dy", "txt_speakerName_dy"},
        {"txt_portrait_name_dy", "txt_portraitName_dy"},
        {"img_dialogue_bg_st", "img_dialogueBg_st"},
        {"txt_reply_hint_dy", "txt_replyHint_dy"},
        {"go_text_area_st", "go_textArea_st"},
        {"btn_end_dialogue_st", "btn_endDialogue_st"},
        {"txt_send_label_st", "txt_sendLabel_st"},
        {"txt_end_dialogue_label_st", "txt_endDialogueLabel_st"},
    };

    private static readonly Dictionary<string, string> DialoguePrefabRenames = new()
    {
        {"UI_DialogueCanvas", "cvs_dialogue_dy"},
        {"DialogueCanvas", "cvs_dialogue_dy"},
        {"BG_Image", "img_bg_dy"},
        {"PortraitImage", "img_portrait_dy"},
        {"PortraitNameLabel", "txt_portraitName_dy"},
        {"DialoguePanel", "pnl_dialogue_dy"},
        {"DialogueBG", "img_dialogueBg_st"},
        {"SpeakerNameLabel", "txt_speakerName_dy"},
        {"DialogueText", "txt_dialogue_dy"},
        {"ChoicesPanel", "pnl_choices_dy"},
        {"ReplyPanel", "pnl_reply_dy"},
        {"ReplyHintLabel", "txt_replyHint_dy"},
        {"ReplyInputField", "inp_reply_dy"},
        {"TextArea", "go_textArea_st"},
        {"Placeholder", "txt_placeholder_st"},
        {"Text", "txt_input_dy"},
        {"SendButton", "btn_send_st"},
        {"SendButton/Label", "txt_sendLabel_st"},
        {"btn_send_st/Label", "txt_sendLabel_st"},
        {"EndDialogueButton", "btn_endDialogue_st"},
        {"EndDialogueButton/Label", "txt_endDialogueLabel_st"},
        {"btn_endDialogue_st/Label", "txt_endDialogueLabel_st"},
    };

    private static readonly Dictionary<string, string> ChoicePrefabRenames = new()
    {
        {"UI_ChoiceButton", "btn_choice_st"},
        {"ChoiceButton", "btn_choice_st"},
        {"ChoiceLabel", "txt_choiceLabel_st"},
    };

    private static readonly Dictionary<string, string> PlayerPrefabRenames = new()
    {
        {"Player_Main", "player_dy"},
        {"Player", "player_dy"},
        {"Capsule", "spr_playerBody_dy"},
    };

    private static readonly Dictionary<string, string> NpcPrefabChildRenames = new()
    {
        {"cav_container", "cvs_bubble_dy"},
        {"img_Bubble", "img_bubble_dy"},
        {"Img_bg", "img_bubbleBg_dy"},
        {"tmp_context", "txt_bubbleContext_dy"},
        {"Panel", "pnl_nameplate_dy"},
        {"Text (TMP)", "txt_nameplate_dy"},
        {"spt_idol", "spr_body_dy"},
    };

    private static readonly Dictionary<string, string> NpcRootNames = new()
    {
        {"Assets/Prefabs/NPCs/Npc_Sakura.prefab", "npc_sakura_dy"},
        {"Assets/Prefabs/NPCs/Npc_Chihaya.prefab", "npc_chihaya_dy"},
        {"Assets/Prefabs/NPCs/Npc_Kazuha.prefab", "npc_kazuha_dy"},
        {"Assets/Prefabs/NPCs/Npc_Tatsunosuke.prefab", "npc_tatsunosuke_dy"},
        {"Assets/Prefabs/NPCs/Npc_Kujo.prefab", "npc_kujo_dy"},
    };

    private static readonly Dictionary<string, string> PrefabRootYamlNames = new()
    {
        {"Assets/Prefabs/UI/UI_DialogueCanvas.prefab", "cvs_dialogue_dy"},
        {"Assets/Prefabs/UI/UI_ChoiceButton.prefab", "btn_choice_st"},
        {"Assets/Prefabs/Player/Player_Main.prefab", "player_dy"},
        {"Assets/Prefabs/NPCs/Npc_Sakura.prefab", "npc_sakura_dy"},
        {"Assets/Prefabs/NPCs/Npc_Chihaya.prefab", "npc_chihaya_dy"},
        {"Assets/Prefabs/NPCs/Npc_Kazuha.prefab", "npc_kazuha_dy"},
        {"Assets/Prefabs/NPCs/Npc_Tatsunosuke.prefab", "npc_tatsunosuke_dy"},
        {"Assets/Prefabs/NPCs/Npc_Kujo.prefab", "npc_kujo_dy"},
    };

    /// <summary>
    /// 规范化当前项目内已有的 scene 与 prefab 命名。
    /// </summary>
    [MenuItem("Tools/Normalize Unity Scene And Prefabs")]
    public static void NormalizeAll()
    {
        RenameAssets();
        NormalizePrefabs();
        NormalizePrefabRootYamlNames();
        NormalizeScene();

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        Debug.Log("[UnityNamingNormalizer] Unity scene/prefab 命名规范化完成。");
    }

    private static void RenameAssets()
    {
        foreach (var (oldPath, newPath) in AssetRenames)
        {
            RenameAssetIfNeeded(oldPath, newPath);
        }

        RenameAssetIfNeeded(OldScenePath, NewScenePath);
    }

    private static void RenameAssetIfNeeded(string oldPath, string newPath)
    {
        if (AssetDatabase.LoadAssetAtPath<Object>(newPath) != null)
            return;

        if (AssetDatabase.LoadAssetAtPath<Object>(oldPath) == null)
            return;

        string newName = System.IO.Path.GetFileName(newPath);
        string error = AssetDatabase.RenameAsset(oldPath, newName);
        if (!string.IsNullOrEmpty(error))
            Debug.LogError($"[UnityNamingNormalizer] 重命名失败: {oldPath} -> {newPath}: {error}");
    }

    private static void NormalizePrefabs()
    {
        RenamePrefabObjects("Assets/Prefabs/UI/UI_DialogueCanvas.prefab", DialoguePrefabRenames);
        RenamePrefabObjects("Assets/Prefabs/UI/UI_ChoiceButton.prefab", ChoicePrefabRenames);
        RenamePrefabObjects("Assets/Prefabs/Player/Player_Main.prefab", PlayerPrefabRenames);

        foreach (var pair in NpcRootNames)
        {
            RenameNpcPrefabObjects(pair.Key, pair.Value);
        }
    }

    private static void NormalizePrefabRootYamlNames()
    {
        foreach (var pair in PrefabRootYamlNames)
        {
            string fullPath = System.IO.Path.GetFullPath(pair.Key);
            if (!System.IO.File.Exists(fullPath))
                continue;

            string text = System.IO.File.ReadAllText(fullPath);
            string expectedLine = $"  m_Name: {pair.Value}";
            if (text.Contains(expectedLine))
                continue;

            string fileName = System.IO.Path.GetFileNameWithoutExtension(pair.Key);
            string oldLine = $"  m_Name: {fileName}";
            if (!text.Contains(oldLine))
                continue;

            text = text.Replace(oldLine, expectedLine);
            System.IO.File.WriteAllText(fullPath, text);
        }

        AssetDatabase.Refresh();
    }

    private static void RenameNpcPrefabObjects(string prefabPath, string rootName)
    {
        var renames = new Dictionary<string, string>(NpcPrefabChildRenames)
        {
            {"Npc_Sakura", rootName},
            {"Npc_Chihaya", rootName},
            {"Npc_Kazuha", rootName},
            {"Npc_Tatsunosuke", rootName},
            {"Npc_Kujo", rootName},
            {"01_Sakura", rootName},
            {"02_Chihaya", rootName},
            {"03_Kazuha", rootName},
            {"04_Tatsunosuke", rootName},
            {"05_Kujo", rootName},
        };

        RenamePrefabObjects(prefabPath, renames);
    }

    private static void RenamePrefabObjects(string prefabPath, Dictionary<string, string> renames)
    {
        if (AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath) == null)
            return;

        GameObject root = PrefabUtility.LoadPrefabContents(prefabPath);
        try
        {
            RenameTransformTree(root.transform, renames);
            PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
        }
        finally
        {
            PrefabUtility.UnloadPrefabContents(root);
        }
    }

    private static void NormalizeScene()
    {
        string scenePath = AssetDatabase.LoadAssetAtPath<SceneAsset>(NewScenePath) != null ? NewScenePath : OldScenePath;
        if (AssetDatabase.LoadAssetAtPath<SceneAsset>(scenePath) == null)
            return;

        var scene = EditorSceneManager.OpenScene(scenePath);
        foreach (var root in scene.GetRootGameObjects())
        {
            RenameTransformTree(root.transform, SceneRenames);
        }

        EditorSceneManager.SaveScene(scene);
    }

    private static void RenameTransformTree(Transform transform, Dictionary<string, string> renames)
    {
        string path = GetRelativePath(transform);
        if (TryResolveName(path, renames, out string byPath))
        {
            transform.name = byPath;
        }
        else if (renames.TryGetValue(transform.name, out string byName))
        {
            transform.name = byName;
        }
        else
        {
            transform.name = NormalizeThreeTagName(transform.name);
        }

        foreach (Transform child in transform)
        {
            RenameTransformTree(child, renames);
        }
    }

    private static bool TryResolveName(string path, Dictionary<string, string> renames, out string newName)
    {
        if (renames.TryGetValue(path, out newName))
            return true;

        foreach (var pair in renames)
        {
            if (pair.Key.Contains("/") && path.EndsWith("/" + pair.Key))
            {
                newName = pair.Value;
                return true;
            }
        }

        newName = null;
        return false;
    }

    private static string NormalizeThreeTagName(string currentName)
    {
        string[] parts = currentName.Split('_');
        if (parts.Length < 3)
            return currentName;

        string stateTag = parts[^1];
        if (stateTag != "st" && stateTag != "dy")
            return currentName;

        if (ComponentTags.Contains(parts[0]) && parts.Length > 2)
        {
            string purposeTag = ToPurposeTag(parts, 1, parts.Length - 2);
            return $"{parts[0]}_{purposeTag}_{stateTag}";
        }

        string purposeOnlyTag = ToPurposeTag(parts, 0, parts.Length - 1);
        return $"{purposeOnlyTag}_{stateTag}";
    }

    private static string ToPurposeTag(string[] parts, int startIndex, int count)
    {
        if (count <= 0)
            return "object";

        for (int i = startIndex + 1; i < startIndex + count; i++)
        {
            if (string.IsNullOrEmpty(parts[i])) continue;
            parts[i] = char.ToUpperInvariant(parts[i][0]) + parts[i][1..];
        }

        parts[startIndex] = char.ToLowerInvariant(parts[startIndex][0]) + parts[startIndex][1..];
        return string.Concat(parts[startIndex..(startIndex + count)]);
    }

    private static string GetRelativePath(Transform transform)
    {
        var names = new List<string>();
        Transform current = transform;
        while (current != null)
        {
            names.Add(current.name);
            current = current.parent;
        }

        names.Reverse();
        return string.Join("/", names);
    }
}
