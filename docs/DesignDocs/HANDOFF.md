# 樱桥通 — AI 社区模拟游戏 交接文档

> 给下一个搭建 Agent 的完整技术规格。讨论上下文见 `MemoryArchitecture.md`。

---

## 1. 项目概览

| 项目 | 内容 |
|------|------|
| **类型** | PC 单机，二次元风格，治愈日常向 |
| **舞台** | 商店街「樱桥通」— 一条 200m 的老街 |
| **玩家** | 22-24 岁，受够 996 从城市回老家，继承奶奶的喫茶店 |
| **NPC** | 5 人，各有店铺（花店/面包店/旧书店/和果子店/派出所） |
| **玩法** | 纯日常，无主线。自由探索、聊天、送礼、旁观 NPC 生活 |
| **LLM** | 云端 Claude/DeepSeek + 本地 BGE Embedding。玩家自带 API Key |

---

## 2. 技术架构

```
Unity 游戏进程 ←── WebSocket(localhost:8765) ──→ Python 后端进程
                ←── REST(localhost:8766) ──→

Python 负责：记忆管理、向量检索、LLM 调用、NPC 行为决策、Prompt 组装
Unity 负责：  场景渲染、动画、UI、导航、输入、对话气泡
```

**为什么不是纯 C#**：Python 有 sentence-transformers + LanceDB + LLM SDK，C# AI 生态为空。

**关键约束**：
- LLM 从不自由生成地点名/行为名 → 只能从预定义 ID 目录中选择
- Python 和 Unity 各自保存一份相同的地点/行为/物品目录 → 双端校验
- Embedding 永远走本地 → 不产生 API 费用

---

## 3. 需要创建的项目结构

```
SakurabashiDoori/
├── backend/                    # Python 后端
│   ├── run.py                  # 入口
│   ├── requirements.txt
│   ├── src/
│   │   ├── main.py             # FastAPI + WebSocket 启动
│   │   ├── config.py           # 加载配置
│   │   ├── api/
│   │   │   ├── websocket.py    # WS 消息路由
│   │   │   └── routes.py       # REST 端点
│   │   ├── database/
│   │   │   ├── sqlite_client.py
│   │   │   └── lancedb_client.py
│   │   ├── memory/
│   │   │   ├── manager.py      # 记忆 CRUD
│   │   │   ├── retrieval.py   # 混合检索
│   │   │   └── embedding.py   # BGE 模型
│   │   ├── npc/
│   │   │   ├── state_manager.py
│   │   │   ├── behavior_engine.py
│   │   │   ├── impression.py
│   │   │   └── reflection.py
│   │   ├── dialogue/
│   │   │   ├── prompt_builder.py
│   │   │   ├── llm_client.py
│   │   │   └── choice_generator.py
│   │   ├── world/
│   │   │   └── clock.py
│   │   └── save/
│   │       └── manager.py
│   ├── config/
│   │   ├── settings.yaml
│   │   ├── npc_profiles/       # sakura.json 等 5 个
│   │   └── prompts/            # system_base.yaml, emotion_tones.yaml
│   ├── data/                   # 运行时数据（gitignore）
│   └── tests/
│
├── unity/                      # Unity 项目
│   └── Assets/
│       ├── Scenes/
│       ├── Scripts/
│       │   ├── Core/           # GameManager, WebSocketClient, TimeController
│       │   ├── NPC/            # NpcController, NpcNavigator, NpcAnimation
│       │   ├── Dialogue/       # PortraitDialogueUI, BubbleUI, BubbleOpacity
│       │   ├── UI/             # MainMenuUI, SaveLoadUI, HudUI
│       │   └── Data/           # CatalogManager, NpcState, MessageTypes
│       ├── Prefabs/NPCs/       # Sakura.prefab 等 5 个
│       ├── Prefabs/UI/         # DialoguePanel, Bubble, ChoiceButton
│       └── Resources/Config/   # locations.json, actions.json, items.json (从 shared/ 复制)
│
├── shared/                     # 唯一数据源，两项目共享
│   ├── locations.json
│   ├── actions.json
│   └── items.json
│
└── docs/DesignDocs/            # 设计文档
    ├── MemoryArchitecture.md
    ├── CharacterPresets.md
    ├── HANDOFF.md              # 本文件
    └── CharacterProfiles/      # 角色立绘生成参考
```

---

## 4. 共享目录（shared/）

### locations.json (9 区, 40+ 点)

```json
{
  "zones": {
    "player_cafe": {
      "spots": ["counter", "window_seat", "table_01", "table_02", "doorway", "kitchen"]
    },
    "flower_shop": {
      "spots": ["counter", "workbench", "window_display", "doorway", "back_room"]
    },
    "bakery": {
      "spots": ["counter", "kneading_table", "oven_area", "display_shelf", "doorway"]
    },
    "bookstore": {
      "spots": ["counter", "reading_sofa", "bookshelf_mystery", "bookshelf_literature", "window_seat", "doorway"]
    },
    "wagashi": {
      "spots": ["counter", "display_case", "back_workbench", "doorway"]
    },
    "police_box": {
      "spots": ["desk", "window_chair", "bench_outside", "doorway"]
    },
    "street": {
      "spots": ["crossroad", "arcade", "vending_machine", "bulletin_board"]
    },
    "park": {
      "spots": ["entrance", "bench_01", "bench_02", "cherry_tree", "fountain", "grass_area"]
    },
    "riverside": {
      "spots": ["bench", "bridge", "cherry_row", "path"]
    }
  }
}
```

### actions.json (7 类, 30+ 行为)

每个行为定义 `action_id`、`category`、`valid_location_types`、`duration_range_sec`。关键行为：

```
移动:  walk_to, enter_shop, leave_shop, go_home
姿态:  stand, sit, lean
工作:  work_craft, work_tend, work_arrange, work_clean, work_open, work_close
休闲:  rest, read, eat, drink, stare_outside, browse, feed_cats
社交:  greet, talk, give_item, observe
反应:  react_surprise, react_embarrassed, react_annoyed, react_grateful, react_avoid, react_hide_pain
特殊:  special_place_flower, special_midnight_walk, special_sneak_delivery, special_hide, special_draw_secretly, special_talk_to_self, special_burst_in, special_cat_talk
```

### items.json (10 个初始物品)

```json
{
  "items": [
    {"id": "baguette", "name": "法棍面包", "category": "food", "source": "bakery"},
    {"id": "melon_bread", "name": "菠萝包", "category": "food", "source": "bakery"},
    {"id": "wagashi_sakura", "name": "樱花和果子", "category": "food", "source": "wagashi"},
    {"id": "canned_coffee", "name": "罐装咖啡", "category": "drink", "source": "vending"},
    {"id": "green_tea", "name": "煎茶", "category": "drink", "source": "shop"},
    {"id": "daisy_bouquet", "name": "雏菊花束", "category": "flower", "source": "flower_shop"},
    {"id": "lily_bouquet", "name": "百合花束", "category": "flower", "source": "flower_shop"},
    {"id": "used_book", "name": "旧书", "category": "other", "source": "bookstore"},
    {"id": "river_stone", "name": "河边的石头", "category": "other", "source": "found"},
    {"id": "pressed_flower", "name": "押花书签", "category": "other", "source": "sakura_gift"}
  ]
}
```

---

## 5. 数据库 Schema（SQLite + LanceDB）

### 节点表
```sql
CREATE TABLE memory_nodes (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    type TEXT NOT NULL,
    value TEXT NOT NULL,
    energy REAL DEFAULT 1.0,
    decay_rate REAL DEFAULT 0.01,
    precision TEXT DEFAULT 'exact',   -- exact|vague|gone
    importance REAL DEFAULT 0.5,
    recall_count INTEGER DEFAULT 0,
    merged_from TEXT,
    original_text TEXT,
    is_core INTEGER DEFAULT 0,
    created_at_game_time TEXT NOT NULL
);
```

### 边表（双向不对称权重）
```sql
CREATE TABLE memory_edges (
    id TEXT PRIMARY KEY,
    node_a TEXT NOT NULL,
    node_b TEXT NOT NULL,
    type TEXT NOT NULL,
    weight_ab REAL DEFAULT 1.0,       -- A → B
    weight_ba REAL DEFAULT 1.0,       -- B → A
    decay_rate_ab REAL DEFAULT 0.01,
    decay_rate_ba REAL DEFAULT 0.01,
    created_at_game_time TEXT
);
```

### 旧表保留
- `npc_states` / `npc_bonds` — 保留（NPC 即时状态和羁绊度数值）
- `short_term_memories` — 保留（7天内原文）
- `player_memories` — 保留（玩家记忆，独立轻量系统）
- ~~`long_term_memory_index`~~ — 废弃，被 `memory_nodes` + `memory_edges` 替代
- ~~`npc_impressions`~~ — 废弃，印象融入人物节点的图结构

### LanceDB
每个 NPC 一个表：`graph_vectors_{npc_id}`。Schema: `node_id`, `vector(1024)`, `type`, `value`, `energy`。

---

## 6. WebSocket 协议

端口：`ws://localhost:8765/ws`

### Unity → Python

| Message | 触发时机 |
|---------|---------|
| `GAME_START {mode, slot}` | 启动/读档后 |
| `BEHAVIOR_COMPLETE {npc_id, command_id, status}` | NPC 行为执行完毕 |
| `PLAYER_MOVE {location_id}` | 玩家到达新位置 |
| `DIALOGUE_START {npc_id, player_location}` | 玩家点击 NPC |
| `PLAYER_CHOICE {choice_id, choice_text}` | 玩家选择对话选项 |
| `DIALOGUE_END {npc_id, reason}` | 对话结束 |
| `FAST_FORWARD {target}` | 快进：pause/evening/tomorrow/cancel |
| `SLEEP` | 玩家去睡觉 |
| `SHOP_STATUS_CHANGE {status}` | open/resting/closed |
| `SAVE_REQUEST {slot}` / `LOAD_REQUEST {slot}` / `GET_SAVES` | 存档操作 |

### Python → Unity

| Message | 触发时机 |
|---------|---------|
| `GAME_READY {mode, game_time, weather, npcs[], player_location}` | 初始化完成 |
| `WAKE_UP {new_game_time, weather, npcs[], dreams_overheard[], save_completed}` | 睡眠反思完成 |
| `GAME_ERROR {error_code, message, recoverable}` | 错误 |
| `GAME_TIME_UPDATE {game_time, time_speed}` | 时间流速变化 |
| `NPC_STATE_UPDATE {npc_id, changes{}}` | NPC 状态变化 |
| `NPC_BEHAVIOR {npc_id, command_id, behavior{action_id, location_id, duration_sec, interruptible}, context{}}` | NPC 行为指令 |
| `BUBBLE_SHOW {npc_id, text, bubble_style, duration_sec}` | 单条气泡 |
| `BUBBLE_SEQUENCE {sequence[{npc_id, text, duration}]}` | 气泡序列 |
| `DIALOGUE_TOKEN {npc_id, token, is_complete}` | 流式对话 token |
| `DIALOGUE_COMPLETE {npc_id, emotion_change, npc_text_complete, choices[]}` | 本轮说完+选项 |
| `DIALOGUE_CLOSE {npc_id, reason}` | 对话中断 |
| `SAVE_COMPLETE` / `LOAD_COMPLETE` / `SAVES_LIST` | 存档操作响应 |

### REST 端点

```
GET  /api/health
GET  /api/saves
GET  /api/npc/{npc_id}/status
GET  /api/npc/{npc_id}/memories?limit=20
GET  /api/player/memories?about_npc=sakura
POST /api/debug/set_time  {day, hour}
```

---

## 7. 游戏时间

```
探索模式：1 游戏分钟 = 3 现实秒 → 1 天 ≈ 30 现实分钟
对话模式：1 游戏分钟 = 30 现实秒（几乎暂停，对话不被打断）
快进模式：10 倍速，玩家随时可停

关键规则：
  • 对话中 NPC routine 自动推迟（不会被时钟压迫）
  • 一天结束 = 玩家选择去睡觉（不是时钟走到 24:00）
  • 错过 NPC 行为没有惩罚
```

---

## 8. 核心系统速览

### 记忆系统（联想记忆图）★ v0.5
- **每个 NPC 一个独立的有向加权图**：节点（概念）+ 边（联想），双向不对称权重
- **"我"节点**：每个 NPC 以"我"自称，energy=1.0 永不衰减
- **11 种节点类型**：自我/人物/时间（3种）/地点（2种）/事件/情绪/感官/物品/话语/反思
- **11 种边类型**：relationship/similar_to/sequenced/happened_at/involved/located_at/felt/contains/associated_with/caused/mentioned
- **四阶段退化**：模糊细节→同类渗透→融合压缩→骨架残留
- **LLM 路由检索**：LLM 只看邻边做路由决策，思考预算控制深度，不走全图遍历
- **四策略选择器**：广度优先/深度优先/最佳优先/最轻松优先（性格+状态决定）
- **每日夜间演化**：衰减 → 建立事件间边 → similar_to 聚类 → 反思生成 → 强化激活路径

### 印象系统（融入图节点）★ v0.5
- 印象 = 图中人物节点的派生属性（周围簇的统计摘要）
- 不再独立存储文本，每次对话时从图结构实时重建
- relationship 边权重 + involved 事件情绪统计 + 关联反思节点 → 重建自然语言印象

### NPC 状态（5 维度）
| 维度 | 类型 | 玩家感知 |
|------|------|----------|
| 情绪（6 种） | 即时 | 直接可见 |
| 精力（0-100） | 即时 | 直接可见 |
| 社交开放度（0-100） | 即时 | 直接可见 |
| 羁绊度（-1~+1） | 持久 | 不可见 |
| 当前心事（自由文本） | 隐藏 | 行为暗示 |

### 行为系统（固定 ID）
- 9 区 40+ 地点 × 30+ 行为 = 位置-行为关联表
- Python 只从目录中选 ID → 双端校验 → 杜绝 LLM 幻觉行为
- 行为优先级：P0 生存 → P1 玩家 → P2 NPC互访 → P3 心事 → P4 日常 → P5 状态 → P6 随机

### 对话 UI（双模式）
- **立绘模式**：玩家主动点击 NPC → 底部对话框 + 立绘 + 选项
- **气泡模式**：NPC 间/NPC 搭话 → 世界气泡，opacity = f(与玩家距离)

### 玩家记忆 → 对话选项
- 玩家记忆（SQLite 单表）→ 检索当前 NPC 相关记忆 → LLM 生成 3-4 个有上下文的选项
- 选项类型：引用过去互动 / 投其所好 / 推进话题 / 通用安全

---

## 9. 五个 NPC

| NPC | 店铺 | 性格 | 核心秘密 |
|-----|------|------|----------|
| 鹿岛樱 24♀ | 花店「花時計」 | 温柔大和抚子 | 心脏病，父母双亡 |
| 千早 23♀ | 面包店「小麦色」 | 热血笨蛋 | 暗恋一人，用送面包表达 |
| 和叶 22♂ | 旧书店「猫之书架」 | 文学闷骚 | 偷偷写小说，想离开但留下 |
| 龙之介 20♂ | 和果子店「龙月堂」 | 社恐宅男 | Pixiv 10 万粉插画师 |
| 九条莲 34♂ | 派出所 | 颓废大叔 | 前刑警，搭档牺牲 |

完整角色设定见 `CharacterProfiles/` 目录下各角色的 md 文件。

---

## 10. Python 依赖

```
fastapi>=0.110
uvicorn[standard]>=0.27
websockets>=12.0
lancedb>=0.6
sentence-transformers>=2.7
anthropic>=0.30
openai>=1.30
pyyaml>=6.0
pydantic>=2.6
```

---

## 11. 建议实现顺序

1. **Python 骨架**：`main.py` + WebSocket 连接 + SQLite 初始化 + 加载 shared/ 目录
2. **冷启动流程**：GAME_START → 初始化数据库 → GAME_READY
3. **Unity 骨架**：场景 + WebSocketClient + 接收 GAME_READY → 放置 NPC
4. **NPC 状态 Tick**：行为决策引擎（先纯规则，后接入 LLM）
5. **对话系统**：立绘模式 + 气泡模式
6. **记忆系统**：短期记忆写入 + LanceDB 向量存储 + 检索
7. **睡眠反思**：每日记忆巩固 + 印象更新 + 心事生成
8. **存档**：文件复制方案

---

## 12. 设计文档索引

| 文档 | 内容 |
|------|------|
| `MemoryArchitecture.md` | **主设计文档** — 图记忆模型、四阶段退化、LLM路由检索、四策略选择器、NPC状态、行为系统（约30章） |
| `memory/graph-memory-model.md` | 图记忆模型独立规格 — 节点/边/预算/策略/路由/演化/DB schema |
| `memory/graph-demo-sakura.md` | 鹿岛樱记忆图可视化演示 — 全景/事件入图/衰减融合/路由追踪/同类渗透 |
| `CharacterPresets.md` | 三套角色预设方案，已选 Preset C |
| `CharacterProfiles/` | 5 个 NPC + 玩家的详细角色设定（立绘生成参考） |
| `MapDesign.md` | 地图设计文档 — 整体布局、店铺内部、公园/河边、Tilemap 规格 |
