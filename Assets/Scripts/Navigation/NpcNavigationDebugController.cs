using UnityEngine;

/// <summary>
/// Play 模式下手动控制指定 NPC 移动到目标地点，用于验证 A* 路径。
/// </summary>
public class NpcNavigationDebugController : MonoBehaviour
{
    [SerializeField] private NpcSpawner _npcSpawner;
    [SerializeField] private string _npcId = "sakura";
    [SerializeField] private string _targetLocationId = "player_cafe";
    [SerializeField] private bool _enableHotkey = true;
    [SerializeField] private KeyCode _moveHotkey = KeyCode.F6;

    /// <summary>
    /// 补齐场景引用，避免调试节点忘记手动拖拽 NpcSpawner。
    /// </summary>
    private void Awake()
    {
        if (_npcSpawner == null)
            _npcSpawner = FindObjectOfType<NpcSpawner>();
    }

    /// <summary>
    /// 检查调试热键并触发 NPC 移动。
    /// </summary>
    private void Update()
    {
        if (_enableHotkey && Input.GetKeyDown(_moveHotkey))
            MoveConfiguredNpc();
    }

    /// <summary>
    /// 控制 Inspector 中指定的 NPC 移动到目标 location_id。
    /// </summary>
    [ContextMenu("Move Configured NPC")]
    public void MoveConfiguredNpc()
    {
        if (_npcSpawner == null)
        {
            Debug.LogWarning("[NpcNavigationDebug] 未找到 NpcSpawner");
            return;
        }

        if (string.IsNullOrEmpty(_npcId) || string.IsNullOrEmpty(_targetLocationId))
        {
            Debug.LogWarning("[NpcNavigationDebug] NPC ID 或目标地点为空");
            return;
        }

        var npc = _npcSpawner.GetNpc(_npcId);
        if (npc == null)
        {
            Debug.LogWarning($"[NpcNavigationDebug] NPC 未生成: {_npcId}");
            return;
        }

        if (!LocationDatabase.HasPosition(_targetLocationId))
        {
            Debug.LogWarning($"[NpcNavigationDebug] 目标地点无坐标: {_targetLocationId}");
            return;
        }

        npc.MoveToLocation(_targetLocationId);
        Debug.Log($"[NpcNavigationDebug] {_npcId} → {_targetLocationId}");
    }
}
