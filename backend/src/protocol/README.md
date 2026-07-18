# Protocol 模块

## 文件夹功能

负责 Unity 与 Python 之间的协议 envelope、版本协商、连接 session、sequence、统一错误和请求幂等。

## 文件夹内容

- `codec.py`: 新 envelope 与旧扁平 JSON 的兼容编解码。
- `session.py`: 单个 WebSocket 连接的 session 和 sequence 校验。
- `deduplication.py`: 有副作用请求的有限容量结果缓存。
- `errors.py`: 稳定协议错误结构。

业务 handler 不应把传输层解析重新塞回 `application/runtime.py`。
