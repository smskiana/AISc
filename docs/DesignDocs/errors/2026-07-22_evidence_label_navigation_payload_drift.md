# 证据标签与导航载荷漂移

## 现象

关系证据列表正确显示方法级 label，例如 `Start -> Load`，但点击后只定位到包含方法的 Class 范围。

## 根本原因

界面从 Method qualified name 生成 label，却从聚合关系的 Class 端点生成导航载荷。展示对象与操作对象来自不同层级，测试又只断言“打开了源码”，因此类级退化未被发现。

## 正确做法

1. 事实证据必须携带自身 source/target symbol ID、qualified name、文件和精确位置。
2. label、description 和 navigation target 必须从同一 evidence record 派生；聚合关系端点不能替代事实端点。
3. 回归测试必须断言具体符号 kind、qualified name 和行号，不能只断言文件被打开。

## 适用范围

IDE QuickPick、关系证据、搜索结果、诊断列表及任何“展示细粒度实体、点击导航到源码”的交互。
