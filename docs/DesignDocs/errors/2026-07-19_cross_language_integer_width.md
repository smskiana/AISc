# 跨语言诊断整数宽度不一致

## 现象

Python 日程 fallback seed 为 `3590737214605091459` 时返回合法 JSON，但 Unity DTO 最初把字段声明为 `int`，Newtonsoft 反序列化抛出 `JsonReaderException`。改成 `long` 后，真实运行又出现接近或超过有符号 Int64 的无符号哈希 seed，说明单纯扩大到 Int64 仍不完整。

## 根本原因

跨端 DTO 只对齐了字段名，没有对齐 Python 无界整数、无符号 64 位哈希、C# 有符号整数和 JavaScript JSON number 精度。稳定 hash/seed 不是算术字段，不应依赖接收端数值类型。

## 正确做法

1. 稳定 hash/seed 跨端按十进制字符串传输；只有需要算术运算的 revision、sequence 和计数才明确协议位宽。
2. 使用 `18446744073709551615` 等无符号 64 位边界字符串做 JSON 反序列化测试。
3. 解析失败诊断应保留响应预览或稳定字段路径，避免只报告笼统 `JsonReaderException`。

## 影响范围

Python/Unity 跨端诊断 DTO、协议 revision/sequence、无符号 hash/seed 和持久化整数。
