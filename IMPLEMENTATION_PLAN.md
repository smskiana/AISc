# Unity 前端执行方案

> 后端已就绪，以下为 Unity 侧设计。

---

## 架构分层

```
┌─────────────────────────────────────────┐
│  UI 层 (Canvas)                         │
│  HUD (时间/天气) | 立绘对话框 | 气泡    │
├─────────────────────────────────────────┤
│  角色层 (SpriteRenderer)                │
│  玩家 | 5 NPC (可移动 Sprite)           │
├─────────────────────────────────────────┤
│  场景层 (Tilemap)                       │
│  商店街主街 | 河岸 | 公园 | 店铺内部    │
└─────────────────────────────────────────┘
        ↕ HTTP POST (localhost:8766/api/ws)
┌─────────────────────────────────────────┐
│  Python 后端                             │
└─────────────────────────────────────────┘
```

---

## Phase U1: 场景搭建 (1-2天)

### U1.1 Tilemap 场景
- **视角**: 侧俯视 2D（类似星露谷）
- **Tilemap**: 使用 Unity 2D Tilemap，3 层
  - Ground 层: 街道/草地/河水
  - Building 层: 店铺外观（7栋）
  - Detail 层: 招牌、樱花树、长椅
- **碰撞**: Tilemap Collider 2D（仅建筑和障碍物）
- **店铺位置**（X轴从左到右）:
  ```
  牌坊 → 小麦色 → 花時計 → 喫茶店 → 猫之书架 → 龙月堂 → 交番
  ```
- **素材**: 先用彩色矩形占位（不用美术资源）
  - 街道: 灰色 200m 长条
  - 店铺: 不同颜色方块（面包店=橙色, 花店=粉色, 喫茶店=棕色, 书店=深蓝, 和果子=紫色, 派出所=灰色）
  - 河: 蓝色
  - 樱花树: 粉色圆点

### U1.2 摄像机
- **正交摄像机 (Orthographic)**
- **分辨率**: 1920×1080 参考
- **跟随玩家**: Cinemachine 或简单脚本（X轴跟随，Y轴轻微跟随）
- **边界**: 限制在商店街范围内

---

## Phase U2: 角色系统 (1天)

### U2.1 玩家控制器
- **移动**: WASD 或 点击地面寻路
- **碰撞**: 与建筑碰撞体交互
- **交互**: 点击 NPC 或走近按 E → 触发对话
- **位置同步**: 移动后发送 PLAYER_MOVE 到后端

### U2.2 NPC 实体
- **NpcEntity 组件**:
  ```
  npcId, currentLocation, currentAction, isTalking
  ```
- **位置更新**: 收到 `NPC_BEHAVIOR` → 移动到 target location
- **简单寻路**: 直线移动到目标位置（NavMesh 后续）
- **状态显示**: 
  - 精力低 → 低头/慢速
  - 社交开放度高 → 在店门口晃
  - 闭店 → 位置移到 back_room（不可见）

### U2.3 NpcSpawner
- 收到 `GAME_READY` → 在对应位置生成 5 个 NPC GameObject
- 建立 npc_id → GameObject 映射

---

## Phase U3: 对话 UI (1-2天)

### U3.1 立绘模式（玩家点击 NPC → 底部对话框）
```
┌─────────────────────────────────────────┐
│                                         │
│         [NPC 立绘]    [对话文字...]      │
│                                         │
├─────────────────────────────────────────┤
│  [选项1]  [选项2]  [选项3]  [选项4]     │
└─────────────────────────────────────────┘
```
- **触发**: 点击 NPC → `DIALOGUE_START`
- **文字显示**: 逐字打印（打字机效果，0.05s/字）
- **选项**: 收到 `DIALOGUE_COMPLETE` 后显示 3-4 个按钮
- **结束**: 按 ESC 或点击关闭 → `DIALOGUE_END`
- **立绘占位**: 纯色方块 + NPC 名字

### U3.2 气泡模式（NPC 间对话 / NPC 搭话玩家）
```
    ┌──────────────┐
    │ 今天天气真好啊 │
    └──────────────┘
       ○ 千早
```
- **世界空间气泡**: 挂在 NPC GameObject 上方
- **距离衰减**: opacity = max(0, 1 - distance/10)
- **持续时间**: 3-5 秒自动消失
- **重叠处理**: 多个气泡错开 Y 偏移

### U3.3 DialogueManager
- 管理对话状态机: `IDLE → TALKING → WAITING_CHOICE → CLOSING`
- 持有对 DialogueUI 和 BubbleUI 的引用
- 处理 `DIALOGUE_TOKEN` / `DIALOGUE_COMPLETE` / `DIALOGUE_CLOSE`

---

## Phase U4: HUD + 时间 (半天)

### U4.1 顶部信息栏
```
[Day 1] [10:30 AM] [☀ sunny]    [存档] [读档]
```
- 收到 `GAME_TIME_UPDATE` 或 `WAKE_UP` 时刷新
- 天气图标切换

### U4.2 睡眠画面
- 收到 `SLEEP_TRIGGER` → 屏幕渐变到黑
- 显示 "zzz..." + 梦话片段（若有）
- 收到 `WAKE_UP` → 屏幕渐亮 → 时间刷新

### U4.3 快进控制
- 喫茶店柜台前 → 显示按钮
- "休息到傍晚" / "休息到午夜" → `FAST_FORWARD`
- 快进中 → 屏幕边缘暗角 + 时间加速动画

---

## Phase U5: 存档 UI (半天)

### U5.1 存档界面
- 按 ESC → 菜单 → 存档/读档
- 显示存档列表（slot、game_day、时间）
- 调用 `SAVE_REQUEST` / `LOAD_REQUEST` / `GET_SAVES`

---

## 实现顺序（推荐）

```
U1.1 场景(Tilemap占位)     ← 立即可做，不依赖后端
U2.1 玩家移动              ← 不依赖后端
U2.2+U2.3 NPC生成+位置     ← 依赖 WS 连接
U3.1 立绘对话              ← 依赖对话系统
U3.3 DialogueManager       ← 集成所有对话逻辑
U4.1 HUD                   ← 依赖时间推送
U3.2 气泡                  ← 可选，锦上添花
U4.2 睡眠画面               ← 依赖 SLEEP_TRIGGER
U5   存档                   ← 依赖 SAVE_REQUEST
```

## 脚本清单

```
Assets/Scripts/
├── Core/
│   ├── GameManager.cs          ✅ 已有
│   ├── WebSocketClient.cs      ✅ 已有
│   └── SceneSetup.cs           ← 新增: 初始化场景+NPC
├── Player/
│   └── PlayerController.cs     ← 新增: 移动+交互
├── NPC/
│   ├── NpcEntity.cs            ← 新增: NPC状态+移动
│   └── NpcSpawner.cs           ← 新增: 生成NPC
├── Dialogue/
│   ├── DialogueManager.cs      ← 新增: 对话状态机
│   ├── PortraitDialogueUI.cs   ← 新增: 立绘对话框
│   └── BubbleUI.cs             ← 新增: 世界气泡
├── UI/
│   ├── HudUI.cs                ← 新增: 时间/天气
│   ├── SleepScreenUI.cs        ← 新增: 睡眠画面
│   └── SaveLoadUI.cs           ← 新增: 存档界面
└── Data/
    └── MessageTypes.cs         ✅ 已有
```

## 关键技术点

| 问题 | 方案 |
|------|------|
| HTTP 桥接无法推送消息 | 用轮询模式：每 0.5s 发一次 PING 获取积压消息 |
| NPC 路径规划 | 初版直线移动，后续替换为 A* 或 Unity NavMesh 2D |
| 对话流式文字 | 收到 token 加入队列，Coroutine 逐字显示 |
| 场景过大 | 2D Tilemap 200m 用 6 个 Chunk（每个 ~30m），超出视口不渲染 |
| 立绘 | 初版用彩色方块占位，后续替换为 Spine/序列帧 |
