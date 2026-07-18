> 设计方案: [2026-07-08_BGE向量图记忆系统_plan.md](2026-07-08_BGE向量图记忆系统_plan.md)

# BGE 向量图记忆系统 v0.6 — 执行记录

## 完成时间
2026-07-08

## 实际改动

### 重写 (6)

| 文件 | 改动 |
|------|------|
| `database/lancedb_client.py` | upsert_node/batch、ANN search、archived管理、批量取值、get_importance |
| `database/sqlite_client.py` | memory_nodes 极简(id+subject_id)、edges clarity_ab/ba+target_importance、边衰减查询 |
| `memory/manager.py` | 边衰减(二次U型)、孤点清理、清晰度恢复、LanceDB写入、JSON修复 |
| `memory/evolution.py` | 去掉similar_to/精度转换/反思，只保留融合(BGE>0.85) |
| `memory/retrieval.py` | 双路召回(图邻边+BGE ANN)、合并排序、LanceDB取值 |
| `npc/state_manager.py` | 冷启动v0.6: LanceDB批量写节点、edges用clarity |

### 修改 (3)

| 文件 | 改动 |
|------|------|
| `main.py` | LanceDB注入、_run_decay→_run_edge_decay、并发提取、玩家记忆提取+搜索 |
| `dialogue/prompt_builder.py` | 移除_derive_impression(70行)、简化为bond值提示词、NPC_MEMORY_LIMIT=2 |
| `config.py` | npc_ids 加 "player" |

### 新建 (1)

| 文件 | 说明 |
|------|------|
| `memory/embedding.py` | BGE-small 512维、国内镜像、pairwise_similarities |

## 移除

- 旧 _derive_impression (70行图查询，v0.6 schema 已不支持)
- similar_to LLM 比较 (BGE 替代)
- 精度转换 (clarity 自然衰减替代)
- 反思生成 (BGE 聚类替代)
- 节点级 clarity (改为边属性)

## 架构变化

```
v0.5: SQLite 存一切 (节点值+能量+衰减+边)
v0.6: SQLite = 联想层(ID+clarity边) | LanceDB = 数据层(向量+值)
      玩家 = LanceDB only (无图)
```

## 验证

- [x] 后端 import 全部通过
- [x] `python run.py` 启动成功 (8张表+6个LanceDB表)
- [x] 5 NPC routines 全部从 profile 加载
- [x] BGE-small 模型就绪 (0.04s/条)
- [ ] Unity Play 端到端测试
- [ ] 午夜演化测试 (边衰减+孤点清理+融合)
- [ ] 玩家对话记忆提取测试
