"""专项 worker 环境、容量和协议损坏测试。"""
from __future__ import annotations
import io
import json
import sys
from pathlib import Path
import threading
from types import SimpleNamespace
import yaml
from backend.src.memory import route_specialist_worker as worker_module
from backend.src.memory.route_specialist_worker import RouteSpecialistWorkerAdapter


def _options() -> dict:
    """提供完整 worker 配置。"""
    return {"model_id": "Qwen/Qwen3-0.6B", "revision": "rev", "adapter_id": "adapter", "adapter_sha256": "0" * 64, "python_env": "TEST_ROUTE_PYTHON", "adapter_path_env": "TEST_ROUTE_ADAPTER", "hf_home_env": "TEST_HF_HOME", "timeout_ms": 100, "max_new_tokens": 32, "restart_cooldown_ms": 0}


def test_missing_environment_is_unavailable(monkeypatch) -> None:
    """缺 Python/Adapter/HF cache 不阻断父进程，只标记 unavailable。"""
    for name in ("TEST_ROUTE_PYTHON", "TEST_ROUTE_ADAPTER", "TEST_HF_HOME"):
        monkeypatch.delenv(name, raising=False)
    adapter = RouteSpecialistWorkerAdapter(_options())
    assert adapter.warmup() == "specialist_unavailable"
    assert adapter.state == "unavailable"


def test_manifest_or_hash_mismatch_is_rejected_before_spawn(tmp_path: Path, monkeypatch) -> None:
    """manifest 和实物 hash 不一致时不得启动子进程。"""
    root = tmp_path / "artifact"
    model_dir = root / "adapter"
    model_dir.mkdir(parents=True)
    (model_dir / "adapter_model.safetensors").write_bytes(b"not-approved")
    (model_dir / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": "Qwen/Qwen3-0.6B"}), encoding="utf-8")
    (root / "run_manifest.yaml").write_text(yaml.safe_dump({"revision": "rev", "tokenizer_revision": "rev"}), encoding="utf-8")
    monkeypatch.setenv("TEST_ROUTE_PYTHON", sys.executable)
    monkeypatch.setenv("TEST_ROUTE_ADAPTER", str(root))
    monkeypatch.setenv("TEST_HF_HOME", str(tmp_path))
    assert RouteSpecialistWorkerAdapter(_options()).warmup() == "specialist_manifest_mismatch"


def test_capacity_one_returns_busy_without_queueing() -> None:
    """已有在途请求时第二个请求立即返回 specialist_busy。"""
    adapter = RouteSpecialistWorkerAdapter(_options())
    adapter._request_lock.acquire()
    try:
        assert adapter.infer({}).reason == "specialist_busy"
    finally:
        adapter._request_lock.release()


def test_invalid_stdout_protocol_terminates_worker() -> None:
    """非法 JSONL 会触发 worker 终止而不是进入响应队列。"""
    adapter = RouteSpecialistWorkerAdapter(_options())
    class _Process:
        """提供损坏 stdout 的最小进程。"""
        stdout = io.StringIO("not-json\n")
    adapter._process = _Process()
    reasons: list[str] = []
    adapter._terminate = reasons.append
    adapter._read_stdout()
    assert reasons == ["specialist_protocol_invalid"]


def test_timeout_terminates_worker_and_enters_cooldown() -> None:
    """有在途请求但无响应时必须超时终止并进入冷却。"""
    class _Input:
        """接受父进程写入的最小 stdin。"""
        def write(self, value):
            return len(value)
        def flush(self):
            return None
    class _Process:
        """模拟持续运行但不返回响应的进程。"""
        stdin = _Input()
        def poll(self):
            return None
        def terminate(self):
            return None
        def wait(self, timeout=None):
            return 0
    adapter = RouteSpecialistWorkerAdapter(_options())
    adapter._process = _Process()
    adapter._ready.set()
    result = adapter.infer({"schema_version": 1})
    assert result.reason == "specialist_timeout"
    assert result.model_call_count == 1
    assert adapter.state == "cooldown"


def test_stdout_eof_marks_unexpected_exit() -> None:
    """未关闭时 stdout EOF 必须标记 exited。"""
    class _Process:
        """提供立即 EOF 的 stdout。"""
        stdout = io.StringIO("")
    adapter = RouteSpecialistWorkerAdapter(_options())
    adapter._process = _Process()
    adapter._read_stdout()
    assert adapter.state == "exited"


def test_first_request_after_cooldown_schedules_only_one_restart(monkeypatch) -> None:
    """损坏 worker 冷却结束后只允许一个后台重启。"""
    adapter = RouteSpecialistWorkerAdapter(_options())
    class _Exited:
        """模拟已经退出的 worker。"""
        def poll(self):
            return 1
    adapter._process = _Exited()
    adapter._set_state("exited")
    starts: list[bool] = []
    monkeypatch.setattr(adapter, "warmup", lambda: starts.append(True))
    class _Thread:
        """同步执行测试目标的线程替身。"""
        def __init__(self, target, **kwargs):
            self.target = target
        def start(self):
            self.target()
    monkeypatch.setattr(worker_module.threading, "Thread", _Thread)
    adapter._schedule_restart()
    adapter._schedule_restart()
    assert starts == [True]
    assert adapter.state == "restarting"


def test_close_is_idempotent_before_start() -> None:
    """未启动和重复关闭均有界完成。"""
    adapter = RouteSpecialistWorkerAdapter(_options())
    adapter.close()
    adapter.close()
    assert adapter.state == "closed"


def test_worker_entry_configures_all_jsonl_streams_as_utf8(monkeypatch) -> None:
    """Windows worker 不得用系统代码页解码父进程 UTF-8 JSONL。"""
    calls: list[tuple[str, str, str]] = []
    class _Stream:
        """记录标准流 reconfigure 参数。"""
        def __init__(self, name: str):
            self.name = name
        def reconfigure(self, **kwargs):
            calls.append((self.name, kwargs["encoding"], kwargs["errors"]))
    monkeypatch.setattr(worker_module.sys, "stdin", _Stream("stdin"))
    monkeypatch.setattr(worker_module.sys, "stdout", _Stream("stdout"))
    monkeypatch.setattr(worker_module.sys, "stderr", _Stream("stderr"))
    worker_module._configure_worker_stdio()
    assert calls == [("stdin", "utf-8", "strict"), ("stdout", "utf-8", "strict"), ("stderr", "utf-8", "backslashreplace")]


def test_worker_requires_cuda_before_loading_nf4_model() -> None:
    """冻结 NF4 worker 在 CUDA 不可用时必须于 READY 前拒绝。"""
    unavailable = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    available = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True))
    assert worker_module._cuda_is_available(unavailable) is False
    assert worker_module._cuda_is_available(available) is True


def test_close_wakes_inflight_infer_without_waiting_for_timeout() -> None:
    """关闭必须立即唤醒正在等待响应的 infer。"""
    written = threading.Event()
    class _Input:
        """记录 infer 已写入并接受 shutdown。"""
        def write(self, value):
            if '"operation":"infer"' in value:
                written.set()
            return len(value)
        def flush(self):
            return None
    class _Process:
        """模拟不返回推理结果的存活进程。"""
        stdin = _Input()
        def poll(self):
            return None
        def wait(self, timeout=None):
            return 0
    adapter = RouteSpecialistWorkerAdapter({**_options(), "timeout_ms": 5000})
    adapter._process = _Process()
    adapter._ready.set()
    results: list[object] = []
    thread = threading.Thread(target=lambda: results.append(adapter.infer({"schema_version": 1})))
    thread.start()
    assert written.wait(0.5)
    adapter.close()
    thread.join(0.5)
    assert not thread.is_alive()
    assert results[0].reason == "specialist_unavailable"
