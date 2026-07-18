"""唯一的 Prompt task 到 messages 组装入口。"""

import logging
from typing import Any

from .prompt_context import PromptContext
from .prompt_registry import PromptRegistry
from .tag_formatter import format_location, format_npc

logger = logging.getLogger("sakurabashi.prompting")


class PromptAssembler:
    """根据 task_id 和结构化上下文渲染 messages。"""

    def __init__(self, registry: PromptRegistry | None = None):
        self.registry = registry or PromptRegistry()

    def build(self, task_id: str, context: PromptContext | dict[str, Any]) -> list[dict[str, str]]:
        """构建任务 messages，并记录不含私密正文的结构诊断。"""
        values = context.as_dict() if isinstance(context, PromptContext) else dict(context)
        values.setdefault("npc_tags", format_npc(values.get("profile", {})))
        values.setdefault("location_tags", format_location(values.get("location_profile")))
        values.setdefault("approach_bias", 0.0)
        values.setdefault("energy", 80)
        values.setdefault("sociability", 50)
        values.setdefault("max_select", 1)
        spec = self.registry.get_task_spec(task_id)
        template = self.registry.get_contract(spec["contract"])
        response = self.registry._responses.get(spec.get("response", ""), "")
        values.setdefault("response_contract", response)
        content = template.format_map(_SafeFormat(values))
        logger.info("prompt task=%s contract=%s keys=%s sections=%s messages=1", task_id, spec["contract"], sorted(values), spec.get("sections", []))
        return [{"role": spec.get("role", "system"), "content": content}]


class _SafeFormat(dict):
    """让兼容字段缺失时输出空值而不是破坏运行。"""

    def __missing__(self, key: str) -> str:
        return "（无）"
