# 后端脚本按文件路径启动时缺少项目根

## 错误现象

新增的 `backend/scripts/evaluate_route_runtime.py` 在 pytest 模块导入中正常，但按文档直接执行 `python backend/scripts/evaluate_route_runtime.py ...` 时立即报 `ModuleNotFoundError: backend`，未进入参数解析或评估。

## 根本原因

Python 按文件路径启动时将脚本所在的 `backend/scripts` 放入 `sys.path[0]`，不会自动加入仓库根。单元测试从仓库根导入模块会掩盖这一差异。

## 正确做法

1. 复用现有后端脚本模式，在导入 `backend.*` 前把 `Path(__file__).parents[2]` 加入 `sys.path`。
2. 新 CLI 至少增加一个从仓库根按文件路径执行 `--help` 的 subprocess 回归。
3. 文档命令与自动化测试必须使用同一种入口形式；不能只测 `import backend.scripts...`。

## 本次修正

运行时 evaluator 已补项目根初始化和 CLI `--help` 回归；随后按文件路径完成 `general_llm / local / r3_v2` 三类真实隔离评估。
