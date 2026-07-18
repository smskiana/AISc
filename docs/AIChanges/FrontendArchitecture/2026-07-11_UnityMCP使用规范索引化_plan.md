> 执行记录: [2026-07-11_UnityMCP使用规范索引化_execution.md](2026-07-11_UnityMCP使用规范索引化_execution.md)

# Unity MCP 使用规范索引化 — 设计方案

## 需求理解

用户希望把 `Unity MCP` 的使用规范从主规则中抽离成单独文件，并由 `rule` 与项目索引统一指向该文件，方便后续继续追加大量资产层建议，而不把 `AGENTS.md` 越写越长。

本轮还需要先落一条明确默认约定：

1. Unity TMP 默认字体通常不完整支持中文
2. 项目内涉及中文显示的 TMP 文本，默认应替换为 `Assets/Fonts/MSYH SDF.asset`

## 方案思路

1. 新建 `docs/DesignDocs/UnityMCPUsageRules.md` 作为 Unity MCP 使用规范主文档
2. 在 `AGENTS.md` / `CLAUDE.md` 中，将 `Unity MCP优先（硬约束）` 收口为“规则摘要 + 明细文档入口”
3. 在 `docs/ProjectIndex.md` 与 `docs/DesignDocs/Index.md` 中补充该文档入口
4. 将 `docs/DesignDocs/ProjectNamingAndIndexing.md` 中原本承载的 Unity 资产层 / MVC 细则改成入口式引用，避免规则重复分散

## 涉及文件

预计修改：

1. `AGENTS.md`
2. `CLAUDE.md`
3. `docs/ProjectIndex.md`
4. `docs/DesignDocs/Index.md`
5. `docs/DesignDocs/ProjectNamingAndIndexing.md`

预计新增：

1. `docs/DesignDocs/UnityMCPUsageRules.md`
2. `docs/AIChanges/FrontendArchitecture/2026-07-11_UnityMCP使用规范索引化_plan.md`
3. `docs/AIChanges/FrontendArchitecture/2026-07-11_UnityMCP使用规范索引化_execution.md`

## 风险点

1. 若与 `ProjectNamingAndIndexing.md` 中已有 Unity 相关内容重复过多，会造成双重来源
2. 若新文档写得过散，反而会让主规则失去可执行性
3. TMP 中文字体规则若不写清“适用范围”和“例外”，后续可能被误用到本就已指定特殊字体的资产

## 本轮收口目标

1. 主规则更短
2. Unity MCP 细则有单独入口
3. 后续新增建议优先往该文档追加，而不是继续膨胀 `AGENTS.md`
