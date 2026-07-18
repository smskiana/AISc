# 2026-07-11: Day 0 被 `or 1` 误覆盖

## 现象

检索输出中，初始背景记忆本应显示：

- `[Day 0]`

却错误显示成：

- `[第1天]`

## 根本原因

读取 `created_day` 时使用了这类写法：

```python
day = node.get("created_day", 1) or 1
```

在 Python 中，`0` 会被当成假值，因此即使 `created_day = 0` 是合法值，也会被 `or 1` 覆盖成 `1`。

## 错误模式

以下模式都属于高风险：

```python
value = data.get("x", 1) or 1
count = raw_count or 0
index = payload.get("index") or default_index
```

只要字段允许合法取值为：

- `0`
- `0.0`
- `False`（视业务而定）
- 空字符串（视业务而定）

就不能直接用 `or 默认值` 做兜底。

## 正确做法

对允许为 `0` 的字段，显式判断 `None`：

```python
day = node.get("created_day")
if day is None:
    day = 1
```

或：

```python
day = node.get("created_day", None)
day = 1 if day is None else day
```

## 适用范围

重点关注以下场景：

1. `created_day`
2. 各类 day / hour / minute / offset / index 字段
3. 计数器
4. 数组索引
5. 排名或优先级字段
6. 可为 `0` 的状态值

## 修改前自查问题

在改相关代码前先问自己：

1. 这个字段的 `0` 是不是合法值？
2. 我是不是用了 `or 默认值`？
3. 我是不是把“缺失值”和“合法 0”混在一起了？

## 本项目中的教训

这个错误之所以危险，是因为它不会抛异常，看起来“代码能跑”，但会悄悄改坏语义层输出。

对记忆系统来说，这类问题尤其麻烦，因为：

1. 输出仍然像是合理中文
2. 但时间语义已经被悄悄篡改
3. 后续调试时很容易误判成检索逻辑或 prompt 问题
