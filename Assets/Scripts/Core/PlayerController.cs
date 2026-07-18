using UnityEngine;

/// <summary>
/// 玩家控制器 — WASD 自由移动 + 点击 NPC 触发对话（需要足够近）。
/// 挂载在玩家 GameObject 上。
/// </summary>
[RequireComponent(typeof(Rigidbody2D))]
public class PlayerController : MonoBehaviour
{
    [Header("移动")]
    [SerializeField] private float _moveSpeed = 5f;
    [SerializeField] private float _npcTalkRange = 3f;   // 与 NPC 对话的最大距离

    [Header("视觉")]
    [SerializeField] private SpriteRenderer _sprite;
    [SerializeField] private Color _movingColor = new Color(1f, 0.9f, 0.7f);

    private Rigidbody2D _rigidbody;
    private Vector2 _movementInput;
    private Color _idleColor;

    /// <summary>
    /// 初始化玩家显示引用和默认颜色。
    /// </summary>
    void Start()
    {
        _rigidbody = GetComponent<Rigidbody2D>();
        if (_rigidbody == null)
            Debug.LogError("[玩家] 缺少 Rigidbody2D，物理移动无法接入碰撞系统。", this);

        if (_sprite == null)
            _sprite = GetComponent<SpriteRenderer>();

        if (_sprite != null)
            _idleColor = _sprite.color;

        // 创建默认方块
        if (_sprite == null)
        {
            var sr = gameObject.AddComponent<SpriteRenderer>();
            var tex = new Texture2D(4, 4);
            var colors = new Color[16];
            for (int i = 0; i < 16; i++) colors[i] = Color.white;
            tex.SetPixels(colors);
            tex.filterMode = FilterMode.Point;
            tex.Apply();
            sr.sprite = Sprite.Create(tex, new Rect(0, 0, 4, 4), new Vector2(0.5f, 0.5f), 4);
            sr.color = new Color(0.3f, 0.6f, 1f);  // 蓝色玩家
            sr.sortingOrder = 10;
            _sprite = sr;
            _idleColor = sr.color;
        }
    }

    /// <summary>
    /// 处理自由移动输入，并允许鼠标点击附近 NPC 开始对话。
    /// </summary>
    void Update()
    {
        var gm = GameManager.Instance;
        if ((gm != null && (!gm.IsGameplayReady || gm.IsDialogueActive))
            || (PauseController.Instance != null
                && PauseController.Instance.IsDomainPaused(PauseTimeDomain.Gameplay)))
        {
            _movementInput = Vector2.zero;
            if (_sprite != null)
                _sprite.color = _idleColor;
            return;
        }

        HandleMovementInput();
        if (Input.GetMouseButtonDown(0))
        {
            HandleClick();
        }
    }

    /// <summary>
    /// 在物理步进中移动玩家，让 Rigidbody2D 参与 2D 碰撞求解。
    /// </summary>
    void FixedUpdate()
    {
        if (_rigidbody == null)
            return;

        Vector2 delta = _movementInput * (_moveSpeed * Time.fixedDeltaTime);
        _rigidbody.MovePosition(_rigidbody.position + delta);
    }

    /// <summary>
    /// 读取 WASD / 方向键输入，执行 2D 平面自由移动。
    /// </summary>
    void HandleMovementInput()
    {
        _movementInput = new Vector2(
            Input.GetAxisRaw("Horizontal"),
            Input.GetAxisRaw("Vertical"));

        if (_movementInput.sqrMagnitude > 1f)
            _movementInput.Normalize();

        if (_sprite != null)
            _sprite.color = _movementInput.sqrMagnitude > 0f ? _movingColor : _idleColor;
    }

    /// <summary>
    /// 鼠标点击 NPC 时尝试对话；不再支持点击地面自动寻路。
    /// </summary>
    void HandleClick()
    {
        Vector3 mouseWorld = Camera.main.ScreenToWorldPoint(Input.mousePosition);
        mouseWorld.z = transform.position.z;

        // 检测是否点击了 NPC
        RaycastHit2D hit = Physics2D.Raycast(mouseWorld, Vector2.zero);
        if (hit.collider != null)
        {
            var npc = hit.collider.GetComponent<NpcEntity>();
            if (npc != null)
            {
                // 自由移动模式下，不再自动走过去，只在范围内允许开聊
                TryTalkToNpc(npc);
                return;
            }
        }
    }

    /// <summary>
    /// 若玩家与 NPC 距离足够近，则请求开始对话。
    /// </summary>
    void TryTalkToNpc(NpcEntity npc)
    {
        if (npc == null) return;

        float dist = Vector3.Distance(transform.position, npc.transform.position);
        if (dist > _npcTalkRange)
        {
            Debug.Log($"[玩家] 离{npc.NpcName}太远({dist:F1}m)，需要靠近一些");
            return;
        }

        var gm = GameManager.Instance;
        if (gm != null)
        {
            string loc = npc.CurrentLocation ?? "player_cafe.doorway";
            var visualContext = npc.CaptureVisualContext(true);
            gm.StartDialogue(npc.NpcId, loc, visualContext);
            Debug.Log($"[玩家] 与{npc.NpcName}({npc.NpcId})对话 @ {loc}");
        }
    }

    void OnDrawGizmosSelected()
    {
        Gizmos.color = Color.yellow;
        Gizmos.DrawWireSphere(transform.position, _npcTalkRange);
    }
}
