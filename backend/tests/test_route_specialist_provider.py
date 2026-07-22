"""专项方向 provider、chain 和 runtime 注册测试。"""
from __future__ import annotations
import asyncio
import json
from types import SimpleNamespace
from backend.src.memory.retrieval_contracts import RetrievalRequest
from backend.src.memory.retrieval_policy import RetrievalPolicyRegistry
from backend.src.memory.route_specialist_provider import ChainedDirectionProvider, DirectionProviderRuntime, R3V2DirectionProvider
from backend.src.memory.route_specialist_worker import WorkerInferenceResult
from backend.src.memory.retrieval_direction import LlmDirectionProvider, LocalDirectionProvider


def _output() -> str:
    """返回完整合法专项方向 JSON。"""
    return json.dumps({"entity_mentions": ["千早"], "location_mentions": [], "themes": ["current_location"], "relation_facets": [], "time_scope": "recent", "source_preferences": ["direct"], "recall_intent": "locate_person", "negative_directions": [], "retrieval_query": "千早在哪里", "query_constraints": ["person_location", "recent"]}, ensure_ascii=False)


class _Worker:
    """返回固定推理结果的 worker。"""
    def __init__(self, result: WorkerInferenceResult):
        self.result = result
    def infer(self, input_payload):
        """返回预设结果。"""
        return self.result


def _options() -> dict:
    """提供冻结模型身份。"""
    return {"model_id": "Qwen/Qwen3-0.6B", "revision": "rev", "adapter_id": "adapter"}


def _runtime_payload() -> dict:
    """显式注册三种 provider，避免能力测试依赖生产默认配置。"""
    import yaml
    from pathlib import Path
    payload = yaml.safe_load((Path(__file__).parents[1] / "config" / "memory_retrieval.yaml").read_text(encoding="utf-8"))
    payload["direction_providers"]["providers"]["r3_v2"] = {
        "kind": "subprocess_specialist", **_options(),
        "adapter_sha256": "0" * 64, "python_env": "MEMORY_ROUTE_PYTHON",
        "adapter_path_env": "MEMORY_ROUTE_R3_V2_ADAPTER", "hf_home_env": "HF_HOME",
        "timeout_ms": 16000, "max_new_tokens": 384, "restart_cooldown_ms": 5000,
    }
    payload["direction_providers"]["default_chain"] = ["r3_v2", "general_llm", "local"]
    return payload


def test_r3_provider_success_preserves_safe_identity() -> None:
    """成功输出采用 r3_v2 并只暴露冻结身份诊断。"""
    provider = R3V2DirectionProvider("r3_v2", _options(), _Worker(WorkerInferenceResult(output=_output(), inference_ms=12, model_call_count=1, worker_state="ready")))
    result = provider.provide(RetrievalRequest(npc_id="sakura", query_text="千早在哪？"), {"query_text": "千早在哪？", "recent_turns": [], "recent_memories": []})
    assert result.source == "r3_v2"
    assert result.failure_reason == ""
    assert result.provider_diagnostics.model_call_count == 1
    assert result.provider_diagnostics.model_id == "Qwen/Qwen3-0.6B"


def test_chain_discards_failed_direction_and_adopts_formal_local() -> None:
    """专项失败后由正式 local 终点生成方向并保留首个失败原因。"""
    r3 = R3V2DirectionProvider("r3_v2", _options(), _Worker(WorkerInferenceResult(reason="specialist_timeout", model_call_count=1, worker_state="cooldown")))
    chain = ChainedDirectionProvider(("r3_v2", "local"), (r3, LocalDirectionProvider()))
    result = chain.provide(RetrievalRequest(npc_id="sakura", query_text="千早在哪？"), {"query_text": "千早在哪？"})
    assert result.source == "local"
    assert result.failure_reason == "specialist_timeout"
    assert result.provider_diagnostics.adopted_provider == "local"
    assert result.provider_diagnostics.fallback_reasons == ("specialist_timeout",)


class _GeneralLlm:
    """返回旧通用方向 provider 可解析的固定 JSON。"""
    is_available = True
    def __init__(self):
        self.calls = 0
    def chat(self, messages, **kwargs):
        """记录一次旧 memory_direction 调用。"""
        self.calls += 1
        return _output()


def test_general_llm_local_chain_preserves_legacy_source_and_call_count() -> None:
    """显式通用 chain 仍采用 source=llm 且只调用一次。"""
    llm = _GeneralLlm()
    chain = ChainedDirectionProvider(("general_llm", "local"), (LlmDirectionProvider(llm=llm), LocalDirectionProvider()))
    result = chain.provide(RetrievalRequest(npc_id="sakura", query_text="千早在哪？"), {"query_text": "千早在哪？"})
    assert llm.calls == 1
    assert result.source == "llm"
    assert result.provider_diagnostics.adopted_provider == "general_llm"
    assert result.provider_diagnostics.model_call_count == 1


def test_runtime_registers_all_configured_provider_kinds() -> None:
    """builder mapping 可构造三种 provider，chain 顺序保持不可变。"""
    runtime = DirectionProviderRuntime(RetrievalPolicyRegistry(payload=_runtime_payload()))
    chain = runtime.chain(("r3_v2", "general_llm", "local"))
    assert chain.provider_ids == ("r3_v2", "general_llm", "local")
    assert len(runtime.health_snapshot()) == 1
    runtime.close()


def test_production_runtime_has_no_specialist_worker() -> None:
    """生产默认只注册本地兼容 provider，不预热专项 worker。"""
    runtime = DirectionProviderRuntime(RetrievalPolicyRegistry())
    assert runtime.health_snapshot() == ()
    assert runtime.warmup() == {}
    runtime.close()


def test_game_runtime_refresh_reuses_direction_provider_runtime(monkeypatch) -> None:
    """存档恢复重建 engine 时必须复用唯一 provider runtime。"""
    from backend.src.application import runtime as runtime_module
    game_runtime = runtime_module.GameRuntime()
    provider_runtime = object()
    game_runtime.direction_provider_runtime = provider_runtime
    prompt_builder = SimpleNamespace(set_state_manager=lambda value: None, set_retrieval=lambda value: None)
    behavior = SimpleNamespace(set_state_manager=lambda value: None)
    services = SimpleNamespace(sqlite=object(), vector_store=None, state_mgr=None, prompt_builder=prompt_builder, mem_mgr=None, retrieval=None, evolution=None, player_events=None, behavior=behavior, npc_dialogue=None)
    game_runtime.services = services
    monkeypatch.setattr(game_runtime, "_get_vector_store", lambda sqlite: object())
    monkeypatch.setattr(runtime_module, "StateManager", lambda sqlite, vector: SimpleNamespace(set_retrieval=lambda value: None))
    monkeypatch.setattr(runtime_module, "MemoryManager", lambda sqlite, vector: SimpleNamespace(recover_clarity=lambda *args: None))
    monkeypatch.setattr(runtime_module, "EvolutionEngine", lambda sqlite, vector: object())
    monkeypatch.setattr(runtime_module, "PlayerEventMemoryWriter", lambda sqlite: object())
    captured: dict[str, object] = {}
    def _init(*args, **kwargs):
        """捕获刷新时注入的 provider runtime。"""
        captured.update(kwargs)
        return object()
    monkeypatch.setattr(runtime_module, "init_retrieval", _init)
    game_runtime._refresh_vector_services()
    assert captured["direction_provider_runtime"] is provider_runtime


def test_game_runtime_stop_closes_provider_runtime() -> None:
    """停止流程在取消业务任务后关闭 provider runtime。"""
    game_runtime = __import__("backend.src.application.runtime", fromlist=["GameRuntime"]).GameRuntime()
    closed: list[bool] = []
    game_runtime.direction_provider_runtime = SimpleNamespace(close=lambda: closed.append(True))
    asyncio.run(game_runtime.stop())
    assert closed == [True]
