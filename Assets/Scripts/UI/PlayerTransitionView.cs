using TMPro;
using UnityEngine;

/// <summary>
/// 玩家场景入口提示视图，只负责提示文本与显隐。
/// </summary>
public class PlayerTransitionView : MonoBehaviour
{
    [SerializeField] private GameObject _root;
    [SerializeField] private TMP_Text _label;

    /// <summary>
    /// 显示指定的场景入口提示。
    /// </summary>
    public void Show(string message)
    {
        if (_label != null)
            _label.text = message;

        if (_root != null)
            _root.SetActive(true);
    }

    /// <summary>
    /// 隐藏场景入口提示。
    /// </summary>
    public void Hide()
    {
        if (_root != null)
            _root.SetActive(false);
    }
}
