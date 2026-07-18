# 后端脚本目录

## 文件夹功能

保存开发期跑测、诊断、数据维护和规范检查脚本。

## 文件夹内容

包括长跑测试、日志分析、数据库检查和项目约定检查。脚本产物应写入指定临时目录或 `docs/AIChanges/artifacts/`。

## 核心入口

- `run_7day_benchmark.py`：隔离运行多日游戏时钟并汇总记忆、行为和性能指标。
- `tune_memory_route_profiles.py`：基于真实记忆图与真实 LLM，二分搜索性能、平衡、质量三档记忆路由阈值。
- `evaluate_deep_retrieval.py`：使用离线固定图和 fake LLM 评估三业务模式 × 三路由策略，输出调用次数、路径、停止原因和向量查询次数。
