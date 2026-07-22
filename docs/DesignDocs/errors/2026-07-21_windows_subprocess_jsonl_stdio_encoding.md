# Windows 子进程 JSONL 标准流代码页错配

## 错误现象

父进程以 UTF-8 `text=True` 管道向本地模型 worker 写入中文 JSONL，但 Windows 子进程的 `sys.stdin` 默认沿用系统代码页。中文输入被解码成孤立 surrogate，后续 chat template 或 tokenizer 先后表现为 `TextEncodeInput` 类型错误和 `UnicodeEncodeError: surrogates not allowed`；协议层只能看到稳定回退，容易误判为 Transformers 输入类型问题。

## 根本原因

`subprocess.Popen(..., encoding="utf-8")` 只规定父进程包装管道时的编码，不会自动重配置子进程内部的 `sys.stdin / sys.stdout / sys.stderr`。父写端与子读端编码不一致时，ASCII 协议字段仍可解析，问题会延迟到包含中文的 payload 被模板或 tokenizer 消费时才暴露。

## 正确做法

1. JSONL worker 入口在读取任何协议行前，对 stdin/stdout 显式 `reconfigure(encoding="utf-8", errors="strict")`，stderr 使用 UTF-8 和不破坏状态日志的有界错误策略。
2. 父进程继续显式声明 `encoding="utf-8"`，stdout 只承载协议，stderr 只承载安全状态。
3. smoke 必须包含至少一条中文输入并走到真实 tokenizer/generate；只验证 ASCII ready/shutdown 无法发现该错误。
4. 看到 tokenizer 输入类型错误时先检查字符是否包含 `U+D800-U+DFFF` surrogate，再判断是否真是 API 类型不兼容。

## 本次修正

R3 v2 worker 入口统一配置三条标准流编码，并增加入口单测。真实 smoke 以中文“千早现在在哪里？”通过 version 1 JSONL 完成一次确定性推理，最终采用 `r3_v2`、模型调用计数为 1，并有界关闭。
