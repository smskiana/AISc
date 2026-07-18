> 设计方案: 本次为文档小修，按约定未单独创建 plan。

# 总规范并入 GameObject 规则 — 执行记录

## 完成时间

2026-07-10

## 需求理解

用户希望把原本单独挂在 `UnityNamingTags.md` 入口下的 `GameObject` 命名规则，也直接并入：

- `docs/DesignDocs/ProjectNamingAndIndexing.md`

目标是让总规范文档本身就能完整承载命名规则，不必只写跳转入口。

## 实际改动清单

### 修改文件 (1)

| 文件 | 实际改动 |
|------|------|
| `docs/DesignDocs/ProjectNamingAndIndexing.md` | 将“GameObject 命名规则入口”扩展为完整规则章节，直接写入格式、字段说明、`st/dy`、示例与执行要求 |

### 新建文件 (1)

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/FrontendArchitecture/2026-07-10_总规范并入GameObject规则_execution.md` | 本次文档迁移执行记录 |

## 写入的核心内容

1. 总规范文档的适用范围不再排除 `GameObject`
2. `GameObject` 命名规则已直接写入总规范文档
3. `UnityNamingTags.md` 保留为标签参考表，而不再只是唯一入口
4. 总规范文档中已明确：
   - 命名格式
   - 字段含义
   - `st / dy` 定义
   - 示例
   - 标签回填规则

## 验证方式

- [x] 已确认 `ProjectNamingAndIndexing.md` 的第 6 节改为完整 `GameObject` 命名规则
- [x] 已确认文档仍保留到 `UnityNamingTags.md` 的参考链接

## 未完成项

- 暂无
