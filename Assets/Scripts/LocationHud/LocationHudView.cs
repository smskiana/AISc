using TMPro;
using UnityEngine;

/// <summary>
/// 显示玩家当前所在大区域名称。
/// </summary>
public sealed class LocationHudView : MonoBehaviour
{
    [SerializeField] private TMP_Text _locationText;

    /// <summary>
    /// 将已解析的显示名写入 HUD。
    /// </summary>
    public void Render(string displayName)
    {
        if (_locationText != null)
            _locationText.text = string.IsNullOrWhiteSpace(displayName) ? "未知" : displayName;
    }
}
