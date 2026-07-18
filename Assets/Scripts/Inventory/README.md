# Inventory 脚本目录

## 文件夹功能

负责玩家运行时背包、共享物品展示配置、只读分组界面和存档桥接。

## 文件夹内容

- `InventoryModel`: 校验、保存和稳定排序物品数量。
- `InventoryController`: 处理 `B` / `Esc` 输入、暂停来源和存档桥接。
- `InventoryView`: 使用分类标题与条目 Prefab 渲染只读列表。
- `ItemCatalog`: 从 `Resources/Config/items.json` 读取稳定 ID、显示名和唯一主分类。

本阶段不实现使用或摧毁物品，但 Model 保留明确的数量写入口供后续命令层扩展。
