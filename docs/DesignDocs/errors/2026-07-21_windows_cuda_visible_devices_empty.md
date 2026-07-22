# Windows 下空 CUDA_VISIBLE_DEVICES 未禁用 GPU

## 错误现象

为复测“CUDA 不可用时 worker 早拒绝”，PowerShell 把 `CUDA_VISIBLE_DEVICES` 设为空字符串。训练子进程仍检测到 CUDA、加载 NF4 模型并进入 READY，产生约 24 秒的假失败证据。

## 根本原因

该 Windows/PyTorch 环境把空字符串视为未设置或不形成有效屏蔽；它不能等价于无可见设备。测试只观察变量存在而不读取 `torch.cuda.is_available()`，会把仍在使用 GPU 的进程误报为 CUDA-disabled。

## 正确做法

1. 使用 `CUDA_VISIBLE_DEVICES=-1` 做显式禁用，并在目标训练 venv 内直接断言 `torch.cuda.is_available() is False`。
2. 真实 smoke 同时记录 warmup 结果、墙钟和健康状态；不得只凭环境变量文本判断。
3. 禁用实验结束后删除环境变量，避免污染后续真实 GPU 测试。

## 本次修正

使用 `CUDA_VISIBLE_DEVICES=-1` 后，正式 worker 在约 2034 ms 返回 `specialist_load_failed`，未进入 READY；冻结 NF4 模型、tokenizer 和 Adapter 均未加载。
