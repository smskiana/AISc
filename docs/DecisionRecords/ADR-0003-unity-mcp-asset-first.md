# ADR-0003: Unity 资产层问题优先使用 Unity MCP

## 状态

Accepted

## 背景

Unity 项目中，场景、Prefab、SerializeField、UI 层级、TMP 字体和编辑器生成流程属于资产层事实。若用运行时代码兜底这些问题，会让场景真实状态和代码假设分离，并增加后续调试成本。

项目规则已经要求 Unity MCP 优先，本 ADR 将该规则作为架构决定固定下来。

## 决定

涉及以下问题时，默认优先使用 Unity MCP 在编辑器资产层解决：

1. 场景对象创建、命名和层级整理。
2. Prefab 结构和 SerializeField 连线。
3. UI 控件摆放、字体、Canvas / Layout 配置。
4. 场景 Anchor、传送点、导航烘焙节点。
5. 编辑器生成或同步资产。

使用 Unity MCP 前必须阅读 `docs/DesignDocs/UnityMCPUsageRules.md`。

## 放弃或暂缓

1. 不用运行时代码长期兜底资产缺失。
2. 不在 MCP 不可用时继续修改资产层相关内容。
3. 不绕过命名与标签规范直接创建历史债。

## 影响

1. 资产层变更应在 execution 中记录 MCP 操作和验证结果。
2. 如果 MCP 不可用，应停止资产层修改并请求下一步指示。
3. 代码层只能处理运行时逻辑，不替代资产层事实。

## 相关入口

1. `docs/DesignDocs/UnityMCPUsageRules.md`
2. `docs/DesignDocs/ProjectNamingAndIndexing.md`
3. `docs/DesignDocs/UnityNamingTags.md`
