"""
LLM 客户端 — 支持 DeepSeek / Anthropic / OpenAI。
"""
import asyncio
import logging
from openai import OpenAI

logger = logging.getLogger("sakurabashi.llm")


class LLMClient:
    """统一的 LLM 调用接口。无 API Key 时自动降级为不可用状态。"""

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        base_url: str = "",
        thinking_mode: str = "",
    ):
        """初始化供应商客户端和可配置的结构化思考模式。"""
        self.provider = provider
        self.model = model
        self.thinking_mode = thinking_mode.strip().lower()
        if self.thinking_mode not in {"", "enabled", "disabled"}:
            raise ValueError("llm.thinking_mode 仅支持 enabled、disabled 或空字符串")
        self.is_available = False

        if not api_key:
            logger.warning(f"LLM 未配置 API Key ({provider})，对话将使用占位文字")
            self.client = None
            return

        if provider in ("deepseek", "openai"):
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = OpenAI(**kwargs)
            self.is_available = True
        else:
            # Anthropic 等其他 provider 后续扩展
            self.client = None

        logger.info(f"LLM: {provider}/{model}")

    def _prepare_request_kwargs(self, kwargs: dict) -> dict:
        """复制请求参数，并按 LongCat 官方格式合并结构化 thinking 字段。"""
        prepared = dict(kwargs)
        if not self.thinking_mode:
            return prepared

        extra_body = dict(prepared.get("extra_body") or {})
        extra_body["thinking"] = {"type": self.thinking_mode}
        prepared["extra_body"] = extra_body
        return prepared

    def chat(self, messages: list[dict], **kwargs) -> str:
        """同步对话（用于轻量路由等非流式场景）"""
        if self.client is None:
            raise RuntimeError(f"LLM 不可用 (provider={self.provider}, key={'set' if self.is_available else 'missing'})")
        request_kwargs = self._prepare_request_kwargs(kwargs)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **request_kwargs,
        )
        return resp.choices[0].message.content

    async def chat_async(self, messages: list[dict], **kwargs) -> str:
        """异步对话"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.chat(messages, **kwargs))

    def chat_stream(self, messages: list[dict], **kwargs):
        """流式对话生成器（用于对话生成）"""
        if self.client is None:
            raise RuntimeError(f"LLM 不可用")
        kwargs["stream"] = True
        request_kwargs = self._prepare_request_kwargs(kwargs)
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **request_kwargs,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat_stream_async(self, messages: list[dict], **kwargs):
        """在线程中读取同步流，并通过异步队列逐 token 交还事件循环。"""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        completed = object()

        def read_stream() -> None:
            """在线程内读取供应商同步流，并安全投递到事件循环。"""
            try:
                for token in self.chat_stream(messages, **kwargs):
                    loop.call_soon_threadsafe(queue.put_nowait, (token, None))
            except Exception as error:
                loop.call_soon_threadsafe(queue.put_nowait, (None, error))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, (completed, None))

        worker = asyncio.create_task(asyncio.to_thread(read_stream))
        try:
            while True:
                token, error = await queue.get()
                if token is completed:
                    break
                if error is not None:
                    raise error
                yield token
        finally:
            await worker


# 全局 LLM 客户端
llm_client: LLMClient = None  # type: ignore


def init_llm(
    provider: str,
    model: str,
    api_key: str,
    base_url: str = "",
    thinking_mode: str = "",
) -> LLMClient:
    """初始化全局 LLM 客户端"""
    global llm_client
    llm_client = LLMClient(provider, model, api_key, base_url, thinking_mode)
    return llm_client
