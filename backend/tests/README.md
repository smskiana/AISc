# 后端测试目录

## 文件夹功能

保存后端自动化测试和测试辅助代码。

## 文件夹内容

按被测功能组织单元测试、集成测试和回归测试。新增测试应靠近对应功能命名，不按日期创建测试目录。

## 何时使用

- Python 纯逻辑、协议契约、数据语义、失败收口和后端集成优先使用本目录测试。
- 先按模块、文件、测试类或测试名运行聚焦测试；只有共享基础模块、协议或数据层受影响时才扩大到完整套件。
- 需要真实 Unity 生命周期、场景状态或资产连线的验证不在本目录模拟，转到 `Assets/Tests/README.md` 和测试与诊断 Workstream。

## 使用规则

1. 新增测试前用 codebase-memory 或 `rg` 查找同一函数、类或契约的既有测试，优先扩展现有文件。
2. 测试记录写明筛选范围、通过/失败/跳过数量和关键失败；涉及运行时业务阶段时结合 `aisc_debug` 结构化证据。
3. 多日跑测、性能、真实 LLM 调优和离线检索评估使用 `backend/scripts/README.md` 中的专用脚本，不塞进普通单测。

记忆检索快速门禁覆盖 policy、方向校准、检索 query、最终原子条目、固定起点和本地/完全 LLM 深搜；`backend/scripts/evaluate_deep_retrieval.py` 用离线固定图在 30 秒内评估九种 mode / strategy 组合，并输出 query 来源、单次向量次数、最终评分分量、淘汰原因和字符量。

R3 v2 运行时独立验收使用 `route_runtime_isolated_factory.py` 与 `fixtures/route_runtime_corpus.jsonl`。factory 每次创建 OS 临时目录中的真实 SQLite/LanceDB，并按显式 provider 构造正式 runtime；禁止把它改为连接正式数据或把 fake probe 结果作为检索级证据。
