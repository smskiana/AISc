# TorchVersion 不能直接写入 PyYAML safe_dump

## 错误现象

LoRA 单步反向传播与 Adapter 保存成功后，`yaml.safe_dump()` 写运行 manifest 时对 `torch.__version__` 抛出 `RepresenterError`，命令最终以失败退出。

## 根本原因

新版本 PyTorch 的 `torch.__version__` 是 `TorchVersion` 对象。它表现得像字符串，但 PyYAML `SafeDumper` 只接受已注册的基础类型，不会自动把该子类当作普通字符串。

## 正确做法

1. 写 JSON/YAML manifest 前，把第三方库版本、CUDA 版本和设备属性显式归一化为基础 `str`、`int`、`float`、`bool`。
2. 把 manifest 写入纳入训练 smoke 的成功条件；反向传播成功不代表可复现产物已经完整落盘。
3. smoke 必须检查进程退出码、Adapter 目录和 manifest 三者同时存在。

## 本次修正

训练脚本对 PyTorch 与 CUDA 版本显式调用 `str()`，重跑后训练、验证、Adapter 保存、manifest 和退出码均成功。

