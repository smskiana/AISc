"""Prompt YAML 注册表。"""

from pathlib import Path
from typing import Any
import yaml


class PromptRegistry:
    """加载并校验 Prompt 任务、契约和标签配置。"""

    def __init__(self, config_dir: str | Path | None = None):
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).resolve().parents[2] / "config" / "prompt"
        self._contracts = self._load("system_contracts.yaml").get("contracts", {})
        self._tasks = self._load("task_specs.yaml").get("tasks", {})
        self._responses = self._load("response_contracts.yaml").get("responses", {})
        self.tag_rendering = self._load("tag_rendering.yaml")
        self.validate()

    def _load(self, name: str) -> dict[str, Any]:
        """读取一个 Prompt YAML 文件。"""
        with (self.config_dir / name).open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream) or {}

    def get_task_spec(self, task_id: str) -> dict[str, Any]:
        """返回任务规格，不暴露业务模块内部配置。"""
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"未知 Prompt task_id: {task_id}") from exc

    def get_contract(self, contract_id: str) -> str:
        """返回系统契约模板。"""
        return self._contracts[contract_id]

    def validate(self) -> None:
        """校验任务引用的系统契约和响应契约完整。"""
        for task_id, spec in self._tasks.items():
            if spec.get("contract") not in self._contracts:
                raise ValueError(f"{task_id} 引用了不存在的 contract")
            response = spec.get("response")
            if response and response not in self._responses:
                raise ValueError(f"{task_id} 引用了不存在的 response contract")
