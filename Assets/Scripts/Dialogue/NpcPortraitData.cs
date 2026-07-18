using UnityEngine;

/// <summary>
/// NPC 立绘数据（一个 NPC 一个 asset）。
/// 在 Project 右键 → Create → Sakurabashi → NPC Portrait Data 创建。
/// </summary>
[CreateAssetMenu(fileName = "Portrait_", menuName = "Sakurabashi/NPC Portrait Data")]
public class NpcPortraitData : ScriptableObject
{
    [Header("绑定")]
    public string NpcId;
    public string NpcName;

    [Header("立绘（按情绪）")]
    public Sprite Default;       // 平静
    public Sprite Happy;         // 开心
    public Sprite Sad;           // 悲伤/低落
    public Sprite Surprised;     // 惊讶
    public Sprite Embarrassed;   // 害羞

    /// <summary>根据情绪名获取对应立绘，找不到返回默认</summary>
    public Sprite GetPortrait(string emotion)
    {
        return emotion switch
        {
            "开心" or "愉快" or "感激" => Happy ? Happy : Default,
            "悲伤" or "低落" or "愧疚" => Sad ? Sad : Default,
            "惊讶" => Surprised ? Surprised : Default,
            "害羞" or "不好意思" => Embarrassed ? Embarrassed : Default,
            _ => Default,
        };
    }
}
