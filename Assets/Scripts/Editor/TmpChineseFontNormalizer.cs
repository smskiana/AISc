using TMPro;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// 编辑器工具：统一把场景和指定 Prefab 中的 TMP 文本切到 MSYH SDF。
/// 菜单: Tools → Apply MSYH SDF Font
/// </summary>
public static class TmpChineseFontNormalizer
{
    public const string ChineseFontAssetPath = "Assets/Fonts/MSYH SDF.asset";
    private static readonly string[] PrefabFolders =
    {
        "Assets/Prefabs/UI",
        "Assets/Prefabs/NPCs",
    };

    [MenuItem("Tools/Apply MSYH SDF Font")]
    public static void ApplyToSceneAndPrefabs()
    {
        var fontAsset = LoadChineseFontAsset();
        if (fontAsset == null)
        {
            Debug.LogError($"[TmpChineseFontNormalizer] 未找到字体资源: {ChineseFontAssetPath}");
            return;
        }

        int sceneChanged = ApplyToScene(fontAsset);
        int prefabChanged = ApplyToPrefabs(fontAsset);

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        Debug.Log($"[TmpChineseFontNormalizer] 已统一字体。Scene={sceneChanged}, Prefab={prefabChanged}");
    }

    /// <summary>
    /// 读取项目内统一使用的中文 TMP 字体资源。
    /// </summary>
    public static TMP_FontAsset LoadChineseFontAsset()
    {
        return AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(ChineseFontAssetPath);
    }

    /// <summary>
    /// 给单个 TMP 文本显式挂上 MSYH SDF 字体和材质。
    /// </summary>
    public static bool ApplyChineseFont(TMP_Text text, TMP_FontAsset fontAsset = null)
    {
        if (text == null) return false;

        fontAsset ??= LoadChineseFontAsset();
        if (fontAsset == null) return false;

        bool changed = false;
        if (text.font != fontAsset)
        {
            text.font = fontAsset;
            changed = true;
        }

        var sharedMaterial = fontAsset.material;
        if (sharedMaterial != null && text.fontSharedMaterial != sharedMaterial)
        {
            text.fontSharedMaterial = sharedMaterial;
            changed = true;
        }

        if (changed)
            EditorUtility.SetDirty(text);

        return changed;
    }

    /// <summary>
    /// 统一当前打开场景中的 TMP 文本。
    /// </summary>
    private static int ApplyToScene(TMP_FontAsset fontAsset)
    {
        int changedCount = 0;
        foreach (var text in Object.FindObjectsOfType<TMP_Text>(true))
        {
            if (ApplyChineseFont(text, fontAsset))
                changedCount++;
        }

        if (changedCount > 0)
            EditorSceneManager.MarkSceneDirty(SceneManager.GetActiveScene());

        return changedCount;
    }

    /// <summary>
    /// 统一 UI 和 NPC 预制体中的 TMP 文本。
    /// </summary>
    private static int ApplyToPrefabs(TMP_FontAsset fontAsset)
    {
        int changedCount = 0;
        string[] prefabGuids = AssetDatabase.FindAssets("t:Prefab", PrefabFolders);
        foreach (string guid in prefabGuids)
        {
            string prefabPath = AssetDatabase.GUIDToAssetPath(guid);
            var root = PrefabUtility.LoadPrefabContents(prefabPath);
            bool prefabChanged = false;

            foreach (var text in root.GetComponentsInChildren<TMP_Text>(true))
            {
                if (ApplyChineseFont(text, fontAsset))
                {
                    changedCount++;
                    prefabChanged = true;
                }
            }

            if (prefabChanged)
                PrefabUtility.SaveAsPrefabAsset(root, prefabPath);

            PrefabUtility.UnloadPrefabContents(root);
        }

        return changedCount;
    }
}
