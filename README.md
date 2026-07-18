# AISc

AISc 是一个以 AI NPC 为核心的 Unity 2D 生活模拟项目。玩家可以在城镇中移动、与 NPC 对话和交互；NPC 则依据日程、世界状态、社交关系与记忆自主选择行为。

项目采用 Unity 客户端与 Python 后端分层架构：Unity 负责场景、角色表现和玩家交互，Python 负责 NPC 决策、对话、记忆、世界状态与存档协作。两端通过 WebSocket 交换结构化协议消息。

## 核心能力

- **AI NPC 行为**：日程规划、行为候选、社交决策和环境感知。
- **对话系统**：流式 NPC 对话、快捷回复、角色称呼与场景感知上下文。
- **图记忆系统**：短期记忆、关系边、初始知识、检索路由与印象更新。
- **地图与导航**：基于网格的 A* 寻路、场景锚点、传送连接和 NPC 移动执行。
- **存档与协议**：Unity 主存档、Python 记忆检查点、重连快照与跨端稳定 ID。
- **AI 诊断接口**：项目专用 `aisc_debug` 与 `aisc_control` 钩子，用于读取结构化运行状态和执行可控验证。

## 技术栈

- 团结引擎 `1.8.5` / Unity `2022.3 LTS`
- C#、uGUI、TextMesh Pro、Cinemachine
- Python 3、FastAPI、Uvicorn、WebSocket
- SQLite、LanceDB、Sentence Transformers
- Anthropic / OpenAI 兼容 LLM Provider

## 目录结构

```text
AISc/
|- Assets/           Unity 客户端脚本、场景、Prefab 与美术资产
|- Packages/         Unity Package Manager 依赖
|- ProjectSettings/  Unity 项目设置
|- backend/          Python 服务、NPC 逻辑、记忆系统与测试
|- shared/           Unity 与 Python 共享的地点、行为和物品配置
`- docs/             Workstream、ADR、设计文档与实施记录
```

更完整的功能导航见 [docs/ProjectIndex.md](docs/ProjectIndex.md)。

## 本地运行

### 1. 启动 Python 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:ANTHROPIC_API_KEY = "your-api-key"
python run.py
```

也可使用 `OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY`，并通过 `LLM_PROVIDER` 和 `LLM_MODEL` 选择供应商与模型。默认服务地址为：

- REST：`http://127.0.0.1:8766`
- WebSocket：`ws://127.0.0.1:8766/ws`

密钥仅应放在环境变量或本地 `backend/config/settings.yaml` 中；该文件已被 Git 忽略，不应提交。

### 2. 启动 Unity 客户端

1. 使用团结引擎 `1.8.5` 或兼容的 Unity `2022.3 LTS` 打开项目根目录。
2. 等待 Package Manager 恢复依赖并完成资产导入。
3. 打开 `Assets/Scenes/Town_Main.scene`，在后端启动后进入 Play Mode。

## 本地依赖说明

为避免泄露授权资产或重分发受限内容，公开仓库不包含以下本地资产：

- `Assets/Plugins/Sirenix/`：Odin Inspector 商业插件，需要自行持有授权并导入。
- `Assets/Fonts/`：本地字体与生成的 TMP 字体资产，需要使用具备再分发权限的字体替代。

部分编辑器工具和导航脚本引用 Odin Inspector，未补齐该依赖时 Unity 可能出现编译错误。

## 测试

```powershell
cd backend
python -m unittest discover -s tests -p "test_*.py"
python scripts/check_project_conventions.py
```

## 文档入口

- [项目功能索引](docs/ProjectIndex.md)
- [路线图](docs/Roadmap.md)
- [Workstream 当前口径](docs/Workstreams/README.md)
- [架构全景](docs/DesignDocs/CodebaseBigPicture.md)
- [架构决策记录](docs/DecisionRecords/README.md)

## 安全提示

不要提交 API Key、个人信息、`backend/data/`、`backend/logs/`、`SaveData/` 或 Unity 生成的 `Library/` 目录。仓库已通过 `.gitignore` 提供基础防护，提交前仍应检查暂存快照。
