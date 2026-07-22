"""R3 v2 provider、通用 provider chain 与方向模型生命周期深模块。"""
from __future__ import annotations

import time
from dataclasses import replace
from typing import Any, Callable

from ..prompting import PromptAssembler
from .retrieval_contracts import DirectionProvider, DirectionProviderAttempt, DirectionProviderConfig, DirectionProviderDiagnostics, DirectionResolution, RetrievalRequest
from .retrieval_direction import LlmDirectionProvider, LocalDirectionProvider
from .retrieval_policy import RetrievalPolicyRegistry
from .route_specialist_contract import SpecialistContractError, SpecialistRouteCodec
from .route_specialist_worker import RouteSpecialistWorkerAdapter


class R3V2DirectionProvider:
    """把同步 DirectionProvider seam 适配到 codec 与本地 worker。"""

    def __init__(self, provider_id: str, options: dict[str, Any], worker: RouteSpecialistWorkerAdapter):
        """注入冻结身份、codec 和单 worker adapter。"""
        self.provider_id = provider_id
        self.options = options
        self.worker = worker
        self.codec = SpecialistRouteCodec()
        self.local = LocalDirectionProvider()

    def provide(self, request: RetrievalRequest, context: dict[str, Any]) -> DirectionResolution:
        """执行一次专项方向推理；失败只返回稳定原因。"""
        input_payload = self.codec.build_input(request, context)
        result = self.worker.infer(input_payload)
        reason = result.reason
        direction = None
        if not reason:
            try:
                direction = self.codec.parse_output(result.output, input_payload)
            except SpecialistContractError as error:
                reason = error.reason
        diagnostics = DirectionProviderDiagnostics(
            requested_provider=self.provider_id,
            chain=(self.provider_id,),
            attempts=(DirectionProviderAttempt(self.provider_id, "failed" if reason else "adopted", reason, result.inference_ms, result.queue_ms, result.model_call_count),),
            model_id=self.options["model_id"], model_revision=self.options["revision"], adapter_id=self.options["adapter_id"], schema_version=1, worker_state=result.worker_state,
        )
        if reason:
            fallback = self.local.provide(request, context)
            return DirectionResolution(fallback.direction, source=self.provider_id, failure_reason=reason, provider_diagnostics=diagnostics)
        return DirectionResolution(direction, source=self.provider_id, provider_diagnostics=replace(diagnostics, adopted_provider=self.provider_id))


class ChainedDirectionProvider:
    """按不可变 provider tuple 选择第一个成功方向。"""

    def __init__(self, provider_ids: tuple[str, ...], providers: tuple[DirectionProvider, ...]):
        """冻结 chain 顺序和对应 provider 实例。"""
        self.provider_ids = provider_ids
        self.providers = providers

    def provide(self, request: RetrievalRequest, context: dict[str, Any]) -> DirectionResolution:
        """逐个尝试 provider，并由正式 local 终点保证可检索。"""
        attempts: list[DirectionProviderAttempt] = []
        first_failure = ""
        identity: DirectionProviderDiagnostics | None = None
        for provider_id, provider in zip(self.provider_ids, self.providers):
            started = time.perf_counter()
            result = provider.provide(request, context)
            nested = result.provider_diagnostics
            if nested and nested.attempts:
                attempts.extend(nested.attempts)
                identity = identity or nested
            else:
                model_call_count = 0 if provider_id == "local" or result.failure_reason == "llm_unavailable" else 1
                attempts.append(DirectionProviderAttempt(provider_id, "failed" if result.failure_reason else "adopted", result.failure_reason, int((time.perf_counter() - started) * 1000), model_call_count=model_call_count))
            if result.failure_reason:
                first_failure = first_failure or result.failure_reason
                continue
            diagnostics = DirectionProviderDiagnostics(
                requested_provider=self.provider_ids[0], adopted_provider=provider_id, chain=self.provider_ids, attempts=tuple(attempts),
                model_id=identity.model_id if identity else "", model_revision=identity.model_revision if identity else "", adapter_id=identity.adapter_id if identity else "", schema_version=identity.schema_version if identity else 1, worker_state=identity.worker_state if identity else "not_applicable",
            )
            return replace(result, failure_reason=first_failure, provider_diagnostics=diagnostics)
        raise RuntimeError("direction_chain_missing_local_terminal")


class DirectionProviderRuntime:
    """注册 provider builder，持有 worker 生命周期并提供冻结 chain。"""

    def __init__(self, registry: RetrievalPolicyRegistry, prompt_assembler: PromptAssembler | None = None, llm: Any = None):
        """按严格配置构建 provider，不在检索 facade 中增长专项分支。"""
        self.registry = registry
        self.prompt_assembler = prompt_assembler or PromptAssembler()
        self.llm = llm
        self._workers: list[RouteSpecialistWorkerAdapter] = []
        builders: dict[str, Callable[[DirectionProviderConfig], DirectionProvider]] = {
            "local": self._build_local,
            "general_llm": self._build_general_llm,
            "subprocess_specialist": self._build_specialist,
        }
        self._providers = {provider_id: builders[config.kind](config) for provider_id, config in registry.direction_providers.providers.items()}

    def _build_local(self, config: DirectionProviderConfig) -> DirectionProvider:
        """构建确定性本地 provider。"""
        return LocalDirectionProvider()

    def _build_general_llm(self, config: DirectionProviderConfig) -> DirectionProvider:
        """构建保持旧行为的通用方向 LLM provider。"""
        return LlmDirectionProvider(self.prompt_assembler, LocalDirectionProvider(), self.llm)

    def _build_specialist(self, config: DirectionProviderConfig) -> DirectionProvider:
        """构建专项 provider 并登记其受管 worker。"""
        worker = RouteSpecialistWorkerAdapter(config.options)
        self._workers.append(worker)
        return R3V2DirectionProvider(config.provider_id, config.options, worker)

    def chain(self, provider_ids: tuple[str, ...]) -> ChainedDirectionProvider:
        """按请求开始时的不可变 ID tuple 返回 provider chain。"""
        return ChainedDirectionProvider(provider_ids, tuple(self._providers[item] for item in provider_ids))

    def local(self) -> DirectionProvider:
        """返回已注册的正式 local provider。"""
        return self._providers["local"]

    def warmup(self) -> dict[str, str]:
        """预热所有专项 worker 并返回稳定状态。"""
        return {str(index): worker.warmup() for index, worker in enumerate(self._workers)}

    def close(self) -> None:
        """幂等关闭全部受管 worker。"""
        for worker in self._workers:
            worker.close()

    def health_snapshot(self) -> tuple[dict[str, Any], ...]:
        """返回不含路径、Prompt 和原始输出的健康快照。"""
        return tuple(worker.health_snapshot() for worker in self._workers)
