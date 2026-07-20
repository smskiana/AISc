# 后端离线训练目录

## 文件夹功能

保存不接入正式运行时的模型数据契约、训练和离线评估工具。模型缓存、训练数据、Adapter、checkpoint 和评估明细必须写到 Git 忽略的项目外产物目录。

## 当前入口

- `memory_route/`：`Qwen3-0.6B + Route LoRA` 记忆检索方向专项模型，详见 `memory_route/README.md`。

本目录不是正式 provider 或运行配置入口；任何 shadow、开发主路由或默认切换都需要新的实施方案。

