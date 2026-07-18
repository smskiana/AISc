# 并行 Python 命令争写同一 pycache

## 错误现象

在 Windows 上并行执行以下两类命令时出现 `WinError 5: 拒绝访问`：

1. `python -m py_compile ...`
2. 导入相同测试模块的 `python -m unittest ...`

两个进程会同时生成并替换同一个 `__pycache__/*.pyc` 临时文件，最终文件替换发生竞争。

## 根本原因

并行化只考虑了命令之间的逻辑独立性，没有考虑 Python 导入和显式编译共享同一缓存写入目标。Windows 对正在被另一个进程占用的目标文件替换更严格，因此其中一个命令失败。

## 正确做法

1. 针对同一组 Python 文件，先串行执行 `py_compile`，再执行单测。
2. 不需要缓存时，可为测试设置 `PYTHONDONTWRITEBYTECODE=1`。
3. 只有确认模块集合和 `__pycache__` 写入目标不重叠时，才并行运行 Python 验证命令。

## 本次修正

改为串行运行编译和单测，并为单测设置 `PYTHONDONTWRITEBYTECODE=1`；随后编译和 4 项单测全部通过。
