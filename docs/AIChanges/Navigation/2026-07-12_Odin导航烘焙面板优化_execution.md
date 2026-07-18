> 设计方案: [2026-07-12_Odin导航烘焙面板优化_plan.md](2026-07-12_Odin导航烘焙面板优化_plan.md)

# Odin 导航烘焙面板优化执行记录

## 实际改动清单

### 烘焙器 Inspector 优化

1. `Assets/Scripts/Navigation/NavigationGridSpriteBaker.cs`
   - 新增 Odin `TitleGroup` / `BoxGroup`，把输出资产、地图 Sprite、障碍物 Sprite、烘焙参数、状态、操作分区。
   - 给 `_targetGrid` 增加 `Required`、`AssetSelector`、`InlineEditor`。
   - 给地图 / 障碍物列表增加折叠列表显示。
   - 新增只读统计：地图 Sprite 数、障碍物 Sprite 数、预估网格尺寸。
   - 新增 Odin 按钮：
     - `Bake 到导航资产`
     - `从地图 Root 收集`
     - `从障碍物 Root 收集`
     - `清空显式列表`
     - `刷新绿→红预览 Sprite`
     - `清空预览 Sprite`
   - 保留原有 `ContextMenu`，不依赖 Odin 按钮才能执行。
   - 新增预览 SpriteRenderer 槽位，可把导航成本场渲染成从绿色到红色的 Sprite。
   - Bake 后可自动刷新预览 Sprite；预览 Sprite 会按导航网格原点和 cellSize 对齐场景。

### 导航资产 Inspector 优化

1. `Assets/Scripts/Navigation/NavigationGridAsset.cs`
   - 新增 Odin 分组：来源、网格、遮罩兼容模式、烘焙结果、移动、传送点、操作。
   - 数据来源使用 `EnumToggleButtons`。
   - 旧遮罩模式字段仅在 `MaskSprite` 来源下显示。
   - 烘焙数组改为隐藏序列化字段，避免 Inspector 被大数组刷屏。
   - 新增只读统计：烘焙格子数、可走格子数、网格尺寸。
   - 新增 `清理运行时缓存` 按钮。

### 工程文件与错误预防

1. `Assembly-CSharp-firstpass.csproj`
   - 移除不存在的 `Assets\Plugins\Sirenix\Odin Inspector\OdinUpgrader.cs` 编译项。
   - 该项是安装 Odin 后的项目文件残留，会导致 `CS2001`。

2. `docs/DesignDocs/errors/2026-07-12_odin_missing_upgrader_csproj.md`
   - 新增 Odin 缺失源文件但 `.csproj` 残留引用的错误明细。

3. `docs/DesignDocs/ErrorPreventionIndex.md`
   - 回写 OdinUpgrader 缺失错误索引。

## 验证方式

1. 执行 `dotnet build AISc.sln --no-restore`。
2. 结果：
   - 0 error。
   - 11 warning。
   - warning 为既有 Unity / Odin 引用冲突、firstpass 无源文件提示、JSON 字段未赋值和 `GameManager._serverUrl` 未使用。

## 未完成项

1. 尚未通过 Unity MCP 在场景中实际创建 `NavigationGridSpriteBaker` 节点。
2. 尚未在 Unity Inspector 中人工检查 Odin 面板视觉效果。
3. 尚未 Play 模式验证 Bake 后 NPC 实际寻路表现。
