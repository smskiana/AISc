"""Prompt 任务使用的轻量结构化上下文。"""

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class PromptContext:
    """承载事实和已压缩片段，不承载任务 Prompt 文案。"""

    values: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """返回供组装器渲染的普通字典。"""
        return dict(self.values)
