using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;
using TMPro;

/// <summary>
/// 单个存档按钮视图：负责显示文案并转发点击事件。
/// </summary>
public class StartMenuSaveButtonView : MonoBehaviour
{
    [SerializeField] private Button _button;
    [SerializeField] private TMP_Text _label;

    /// <summary>
    /// 绑定按钮文案和点击动作。
    /// </summary>
    public void Bind(string label, UnityAction onClick)
    {
        if (_label != null)
            _label.text = label;

        if (_button == null)
            return;

        _button.onClick.RemoveAllListeners();
        if (onClick != null)
            _button.onClick.AddListener(onClick);
    }

    public void SetInteractable(bool interactable)
    {
        if (_button != null)
            _button.interactable = interactable;
    }

#if UNITY_EDITOR
    /// <summary>
    /// 编辑器下自动补抓常用引用，减少预制体漏绑。
    /// </summary>
    private void OnValidate()
    {
        if (_button == null)
            _button = GetComponent<Button>();

        if (_label == null)
            _label = GetComponentInChildren<TextMeshProUGUI>(true);
    }
#endif
}
