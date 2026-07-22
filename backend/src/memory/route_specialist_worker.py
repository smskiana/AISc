"""R3 v2 方向模型的轻量父进程 adapter 与延迟导入 worker 入口。"""
from __future__ import annotations

import hashlib
import builtins
import json
import logging
import os
import queue
import re
import subprocess
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .route_specialist_contract import SpecialistRouteCodec

logger = logging.getLogger("sakurabashi.retrieval.specialist_worker")
PROTOCOL_VERSION = 1
MAX_PROTOCOL_LINE = 65536


@dataclass(frozen=True)
class WorkerInferenceResult:
    """父进程可消费的安全推理结果。"""
    output: str = ""
    reason: str = ""
    inference_ms: int = 0
    queue_ms: int = 0
    model_call_count: int = 0
    worker_state: str = "unavailable"


class RouteSpecialistWorkerAdapter:
    """管理单个容量为 1 的本地专项模型子进程。"""

    def __init__(self, options: dict[str, Any]):
        """保存已由 policy 严格校验的 worker 选项。"""
        self.options = dict(options)
        self._process: subprocess.Popen[str] | None = None
        self._state = "not_started"
        self._state_lock = threading.Lock()
        self._request_lock = threading.Lock()
        self._ready = threading.Event()
        self._startup_complete = threading.Event()
        self._startup_reason = ""
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=4)
        self._closed = False
        self._cooldown_until = 0.0
        self._restart_used = False
        self._restart_lock = threading.Lock()

    @property
    def state(self) -> str:
        """返回不含路径和输入内容的只读 worker 状态。"""
        with self._state_lock:
            return self._state

    def health_snapshot(self) -> dict[str, Any]:
        """返回只含冻结身份和状态的安全健康快照。"""
        return {"state": self.state, "model_id": self.options["model_id"], "revision": self.options["revision"], "adapter_id": self.options["adapter_id"], "schema_version": 1}

    def warmup(self) -> str:
        """校验外部资产并启动 worker，失败只改变 provider 可用性。"""
        if self._closed:
            return "specialist_unavailable"
        if self._process and self._process.poll() is None:
            return "" if self._ready.is_set() else "specialist_unavailable"
        if time.monotonic() < self._cooldown_until:
            return "specialist_unavailable"
        reason, python_path, adapter_path, hf_home = self._validate_environment()
        if reason:
            self._set_state(reason.removeprefix("specialist_"))
            return reason
        env = os.environ.copy()
        env[self.options["hf_home_env"]] = str(hf_home)
        env["MEMORY_ROUTE_WORKER_CONFIG"] = json.dumps({key: self.options[key] for key in ("model_id", "revision", "adapter_id", "max_new_tokens")}, separators=(",", ":"))
        env["MEMORY_ROUTE_WORKER_ADAPTER"] = str(adapter_path)
        self._ready.clear()
        self._startup_complete.clear()
        self._startup_reason = ""
        self._set_state("loading")
        try:
            self._process = subprocess.Popen([str(python_path), "-m", "backend.src.memory.route_specialist_worker"], cwd=str(Path(__file__).resolve().parents[3]), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError:
            self._set_state("unavailable")
            return "specialist_unavailable"
        threading.Thread(target=self._read_stdout, name="route-specialist-stdout", daemon=True).start()
        threading.Thread(target=self._read_stderr, name="route-specialist-stderr", daemon=True).start()
        wait_seconds = min(120.0, max(30.0, int(self.options["timeout_ms"]) / 1000.0 * 6))
        if not self._startup_complete.wait(wait_seconds):
            reason = "specialist_unavailable"
            self._terminate(reason)
            return reason
        if self._closed:
            return "specialist_unavailable"
        if not self._ready.is_set():
            reason = self._startup_reason or "specialist_load_failed"
            self._terminate(reason)
            return reason
        return ""

    def infer(self, input_payload: dict[str, Any]) -> WorkerInferenceResult:
        """非阻塞占用 worker，并等待一个有界的匹配响应。"""
        queued = time.perf_counter()
        if not self._request_lock.acquire(blocking=False):
            return WorkerInferenceResult(reason="specialist_busy", worker_state=self.state)
        try:
            queue_ms = int((time.perf_counter() - queued) * 1000)
            process = self._process
            if self._closed or not self._ready.is_set() or process is None or process.poll() is not None or process.stdin is None:
                self._schedule_restart()
                return WorkerInferenceResult(reason="specialist_unavailable", queue_ms=queue_ms, worker_state=self.state)
            request_id = uuid.uuid4().hex
            message = {"protocol_version": 1, "request_id": request_id, "operation": "infer", "input": input_payload}
            try:
                process.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError):
                self._terminate("specialist_worker_exited")
                return WorkerInferenceResult(reason="specialist_worker_exited", queue_ms=queue_ms, model_call_count=1, worker_state=self.state)
            try:
                response = self._responses.get(timeout=int(self.options["timeout_ms"]) / 1000.0)
            except queue.Empty:
                self._terminate("specialist_timeout")
                return WorkerInferenceResult(reason="specialist_timeout", queue_ms=queue_ms, model_call_count=1, worker_state=self.state)
            if response.get("event") == "closed":
                return WorkerInferenceResult(reason="specialist_unavailable", queue_ms=queue_ms, model_call_count=1, worker_state=self.state)
            if response.get("protocol_version") != 1 or response.get("request_id") != request_id or response.get("status") not in {"ok", "error"}:
                self._terminate("specialist_protocol_invalid")
                return WorkerInferenceResult(reason="specialist_protocol_invalid", queue_ms=queue_ms, model_call_count=1, worker_state=self.state)
            if response["status"] == "error":
                reason = str(response.get("reason") or "specialist_load_failed")
                return WorkerInferenceResult(reason=reason, inference_ms=int(response.get("inference_ms", 0)), queue_ms=queue_ms, model_call_count=1, worker_state=self.state)
            return WorkerInferenceResult(output=str(response.get("output", "")), inference_ms=int(response.get("inference_ms", 0)), queue_ms=queue_ms, model_call_count=1, worker_state=self.state)
        finally:
            self._request_lock.release()

    def close(self) -> None:
        """幂等、有界地 shutdown、terminate，最后才 kill worker。"""
        self._closed = True
        self._set_state("closing")
        self._ready.set()
        self._startup_complete.set()
        try:
            self._responses.put_nowait({"event": "closed"})
        except queue.Full:
            pass
        process = self._process
        if process is None:
            self._set_state("closed")
            return
        try:
            if process.poll() is None and process.stdin:
                process.stdin.write('{"protocol_version":1,"operation":"shutdown"}\n')
                process.stdin.flush()
                process.wait(timeout=1.5)
        except (OSError, subprocess.TimeoutExpired):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1.0)
        self._ready.clear()
        self._set_state("closed")

    def _validate_environment(self) -> tuple[str, Path, Path, Path]:
        """解析环境变量，并校验 Python、manifest、revision 和 Adapter hash。"""
        python_path = Path(os.getenv(self.options["python_env"], ""))
        configured_adapter = Path(os.getenv(self.options["adapter_path_env"], ""))
        hf_home = Path(os.getenv(self.options["hf_home_env"], ""))
        adapter_path = configured_adapter if (configured_adapter / "adapter_model.safetensors").is_file() else configured_adapter / "adapter"
        if not python_path.is_file() or not adapter_path.is_dir() or not hf_home.is_dir():
            return "specialist_unavailable", python_path, adapter_path, hf_home
        model_file = adapter_path / "adapter_model.safetensors"
        config_file = adapter_path / "adapter_config.json"
        manifest_file = adapter_path.parent / "run_manifest.yaml"
        if not model_file.is_file() or not config_file.is_file() or not manifest_file.is_file():
            return "specialist_manifest_mismatch", python_path, adapter_path, hf_home
        try:
            adapter_config = json.loads(config_file.read_text(encoding="utf-8"))
            manifest = yaml.safe_load(manifest_file.read_text(encoding="utf-8")) or {}
            digest = hashlib.sha256(model_file.read_bytes()).hexdigest()
        except (OSError, ValueError, yaml.YAMLError):
            return "specialist_manifest_mismatch", python_path, adapter_path, hf_home
        valid = adapter_config.get("base_model_name_or_path") == self.options["model_id"] and manifest.get("revision") == self.options["revision"] and manifest.get("tokenizer_revision") == self.options["revision"] and digest == self.options["adapter_sha256"]
        return ("" if valid else "specialist_manifest_mismatch"), python_path, adapter_path, hf_home

    def _read_stdout(self) -> None:
        """在独立线程读取 versioned JSONL，避免 Windows pipe select。"""
        process = self._process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            if len(line) > MAX_PROTOCOL_LINE:
                self._terminate("specialist_protocol_invalid")
                return
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                self._terminate("specialist_protocol_invalid")
                return
            if message.get("protocol_version") != 1:
                self._terminate("specialist_protocol_invalid")
                return
            if message.get("event") == "ready":
                self._set_state("ready")
                self._ready.set()
                self._startup_complete.set()
            elif message.get("event") == "fatal":
                self._set_state("load_failed")
                self._startup_reason = str(message.get("reason") or "specialist_load_failed")
                self._startup_complete.set()
            else:
                try:
                    self._responses.put_nowait(message)
                except queue.Full:
                    self._terminate("specialist_protocol_invalid")
                    return
        if not self._closed and self.state not in {"load_failed", "cooldown"}:
            self._set_state("exited")
            self._ready.clear()
            self._cooldown_until = time.monotonic() + int(self.options["restart_cooldown_ms"]) / 1000.0
            self._startup_reason = "specialist_worker_exited"
            self._startup_complete.set()

    def _read_stderr(self) -> None:
        """消费 stderr 且只记录安全状态，不转发模型输入或原始输出。"""
        process = self._process
        if process is None or process.stderr is None:
            return
        for line in process.stderr:
            safe = line.strip()
            if re.fullmatch(r"status=[a-z_]+ stage=[a-z_]+ error_type=[A-Za-z]+ frames=[A-Za-z0-9_?>]+ detail=[A-Za-z0-9_ .:=(),'?\-]+", safe):
                logger.warning("specialist worker %s", safe)
            else:
                logger.debug("specialist worker stderr event chars=%d", len(safe))

    def _terminate(self, reason: str) -> None:
        """终止损坏 worker 并进入固定冷却。"""
        process = self._process
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()
        self._ready.clear()
        self._cooldown_until = time.monotonic() + int(self.options["restart_cooldown_ms"]) / 1000.0
        self._set_state("cooldown")
        logger.warning("specialist worker stopped reason=%s", reason)

    def _schedule_restart(self) -> None:
        """冷却结束后的首个请求至多触发一次后台重启。"""
        if self._closed or self._restart_used or self.state not in {"exited", "cooldown", "load_failed"} or time.monotonic() < self._cooldown_until:
            return
        process = self._process
        if process is not None and process.poll() is None:
            return
        with self._restart_lock:
            if self._restart_used:
                return
            self._restart_used = True
            self._set_state("restarting")
            threading.Thread(target=self.warmup, name="route-specialist-restart", daemon=True).start()

    def _set_state(self, state: str) -> None:
        """在线程间原子更新安全状态。"""
        with self._state_lock:
            self._state = state


def _emit(message: dict[str, Any]) -> None:
    """向 stdout 写出唯一协议行。"""
    sys.stdout.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _configure_worker_stdio() -> None:
    """在 Windows 子进程入口强制 JSONL 三条标准流使用 UTF-8。"""
    sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")


def _cuda_is_available(torch_module: Any) -> bool:
    """冻结 NF4 worker 只在 CUDA 可用时允许进入模型加载。"""
    return bool(torch_module.cuda.is_available())


def _worker_main() -> int:
    """延迟加载模型并处理 version 1 JSONL 请求。"""
    _configure_worker_stdio()
    try:
        config = json.loads(os.environ["MEMORY_ROUTE_WORKER_CONFIG"])
        adapter_path = os.environ["MEMORY_ROUTE_WORKER_ADAPTER"]
        import torch
        if not _cuda_is_available(torch):
            _emit({"protocol_version": 1, "event": "fatal", "reason": "specialist_load_failed"})
            return 2
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True, bnb_4bit_quant_type="nf4")
        tokenizer = AutoTokenizer.from_pretrained(adapter_path, local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(config["model_id"], revision=config["revision"], local_files_only=True, quantization_config=quantization, device_map="auto")
        model = PeftModel.from_pretrained(model, adapter_path)
        model.eval()
    except Exception:
        _emit({"protocol_version": 1, "event": "fatal", "reason": "specialist_load_failed"})
        return 2
    codec = SpecialistRouteCodec()
    _emit({"protocol_version": 1, "event": "ready", "model_id": config["model_id"], "revision": config["revision"], "adapter_id": config["adapter_id"], "schema_version": 1})
    for line in sys.stdin:
        started = time.perf_counter()
        stage = "protocol"
        try:
            message = json.loads(line)
            if message.get("protocol_version") != 1:
                raise ValueError("protocol")
            if message.get("operation") == "shutdown":
                return 0
            if message.get("operation") != "infer" or not isinstance(message.get("input"), dict):
                raise ValueError("protocol")
            request_id = str(message["request_id"])
            stage = "messages"
            messages = codec.messages(message["input"])
            stage = "render_template"
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            if isinstance(prompt, list) and len(prompt) == 1 and isinstance(prompt[0], builtins.str):
                prompt = prompt[0]
            if not isinstance(prompt, builtins.str):
                raise TypeError(f"chat_template_return_type_{type(prompt).__name__}")
            prompt = builtins.str(prompt).encode("utf-8").decode("utf-8")
            stage = "tokenize"
            encoded = tokenizer.backend_tokenizer.encode(prompt, add_special_tokens=False)
            input_ids = torch.tensor([encoded.ids], dtype=torch.long)
            inputs = {"input_ids": input_ids, "attention_mask": torch.ones_like(input_ids)}
            stage = "device_move"
            inputs = {key: value.to(model.device) for key, value in inputs.items()}
            stage = "generate"
            with torch.inference_mode():
                generated = model.generate(**inputs, do_sample=False, max_new_tokens=int(config["max_new_tokens"]))
            stage = "decode"
            input_length = inputs["input_ids"].shape[-1]
            output = tokenizer.decode(generated[0][input_length:], skip_special_tokens=True).strip()
            stage = "emit"
            _emit({"protocol_version": 1, "request_id": request_id, "status": "ok", "output": output, "inference_ms": int((time.perf_counter() - started) * 1000)})
        except Exception as error:
            detail = re.sub(r"[^A-Za-z0-9_ .:=(),'?\-]", "?", str(error))[:240]
            frames = ">".join(item.name for item in traceback.extract_tb(error.__traceback__)[-5:])
            sys.stderr.write(f"status=infer_error stage={stage} error_type={type(error).__name__} frames={frames} detail={detail}\n")
            sys.stderr.flush()
            _emit({"protocol_version": 1, "request_id": str(locals().get("message", {}).get("request_id", "")), "status": "error", "reason": "specialist_protocol_invalid", "inference_ms": int((time.perf_counter() - started) * 1000)})
    return 0


if __name__ == "__main__":
    raise SystemExit(_worker_main())
