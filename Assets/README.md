# Unity 资产目录说明

## 文件夹功能

保存 Unity 客户端运行时代码、编辑器工具、场景、Prefab、配置数据和游戏视觉资源。查找具体功能时，先按下表进入对应目录；脚本实现从 `Scripts/README.md` 继续定位。

## 目录入口

| 目录 | 功能 | 优先入口 |
|------|------|----------|
| `Scripts/` | Unity 运行时与编辑器脚本 | [Scripts/README.md](Scripts/README.md) |
| `Scenes/` | 正式场景与场景级对象 | 按场景名定位，资产层修改遵循 Unity MCP 规范 |
| `Prefabs/` | 可复用 GameObject、NPC 与 UI 预制体 | 按功能目录和 Prefab 名定位 |
| `Data/` | Unity 侧配置与数据资产 | 结合 `Scripts/Data/` 的模型和读取逻辑定位 |
| `Resources/` | 需要通过 Unity Resources 机制加载的资产 | 按运行时资源路径定位 |
| `Art/`、`Sprites/` | 美术源资源、图片与 Sprite | 按业务对象和资源类型定位 |
| `Fonts/` | 项目字体与 TMP 字体资产 | 中文 TMP 默认字体见 [UnityMCPUsageRules.md](../docs/DesignDocs/UnityMCPUsageRules.md) |
| `Materials/`、`Shaders/` | 材质与 Shader | 结合使用它们的场景、Prefab 或组件定位 |
| `Tests/` | Unity EditMode / PlayMode 测试 | 按被测功能或测试类名定位 |
| `Plugins/`、`TextMesh Pro/` | 第三方插件和 Unity 管理内容 | 非项目业务代码入口，避免无关修改 |
| `Screenshots/` | 截图与视觉验证产物 | 按验证目标定位，不作为运行时入口 |

## 查找规则

1. 脚本问题先进入 `Scripts/README.md`，再按功能子目录 README 和具体符号搜索。
2. 场景、Prefab、UI、SerializeField 连线和编辑器资产配置先阅读 [UnityMCPUsageRules.md](../docs/DesignDocs/UnityMCPUsageRules.md)，并优先通过 Unity MCP 处理。
3. 资源命名与目录索引遵循 [ProjectNamingAndIndexing.md](../docs/DesignDocs/ProjectNamingAndIndexing.md)；GameObject、Prefab 和 UI 层级标签同时参考 [UnityNamingTags.md](../docs/DesignDocs/UnityNamingTags.md)。
4. 普通素材叶子文件通过目录、资源名和 `rg` 定位，不在本 README 逐项登记。
5. `Plugins/`、`TextMesh Pro/` 等第三方或 Unity 管理目录不机械补充项目 README。
