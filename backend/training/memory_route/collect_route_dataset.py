"""从批准的离线候选输入生成待人工复核的记忆路由数据。"""

from __future__ import annotations

import argparse
import importlib
import os
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from backend.src.dialogue.llm_client import LLMClient
from backend.src.memory.retrieval_contracts import DirectionResolution, RetrievalRequest
from backend.src.memory.retrieval_direction import DirectionResolver, LlmDirectionProvider
from backend.src.prompting import PromptAssembler
from backend.training.memory_route.common import (
    SYSTEM_PROMPT,
    assign_grouped_splits,
    append_jsonl,
    direction_from_payload,
    direction_to_payload,
    iter_jsonl,
    write_jsonl,
)


class StaticDirectionProvider:
    """把候选原始方向送入正式 DirectionResolver 校准链。"""

    def __init__(self, payload: dict[str, Any]):
        """保存单条候选方向。"""
        self._direction = direction_from_payload(payload)

    def provide(self, request: RetrievalRequest, context: dict[str, Any]) -> DirectionResolution:
        """返回原始方向，后续验证与校准仍由正式 resolver 负责。"""
        return DirectionResolution(direction=self._direction, source="offline_candidate")


class DiagnosticTeacherClient:
    """为离线教师调用保留脱敏、截断的失败诊断。"""

    def __init__(self, client: LLMClient, api_key: str):
        """包装正式客户端，并保存仅用于本地报错的密钥脱敏值。"""
        self._client = client
        self._api_key = api_key
        self.is_available = client.is_available
        self._last_response = ""
        self._last_error = ""

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """转发教师请求，并记录响应或异常供采集失败时定位。"""
        self._last_response = ""
        self._last_error = ""
        try:
            response = self._client.chat(messages, **kwargs)
            self._last_response = str(response or "")
            return response
        except Exception as error:
            self._last_error = f"{type(error).__name__}:{error}"
            raise

    def diagnostic_summary(self) -> str:
        """返回不含 API Key 的单行截断诊断。"""
        if self._last_error:
            summary = f"teacher_request_error:{self._last_error}"
        elif self._last_response:
            preview = self._last_response.replace("\r", " ").replace("\n", " ")
            summary = f"teacher_response_not_valid_json:{preview}"
        else:
            summary = "teacher_no_response_diagnostic"
        return summary.replace(self._api_key, "<redacted>")[:800]


class StrictTrainingPromptAssembler:
    """在正式方向 Prompt 前注入训练 schema 的完整白名单。"""

    def __init__(self, base: PromptAssembler | None = None):
        """复用正式 PromptAssembler，不复制运行时上下文模板。"""
        self._base = base or PromptAssembler()

    def build(self, task_id: str, context: dict[str, Any]) -> list[dict[str, str]]:
        """为离线教师返回 system schema 与正式 user prompt。"""
        return [{"role": "system", "content": SYSTEM_PROMPT}, *self._base.build(task_id, context)]


def _load_engine(factory_spec: str) -> Any:
    """从 module:function 工厂加载只读隔离 RetrievalEngine。"""
    module_name, separator, function_name = factory_spec.partition(":")
    if not separator:
        raise ValueError("engine_factory_must_be_module_colon_function")
    factory = getattr(importlib.import_module(module_name), function_name)
    engine = factory()
    if not callable(getattr(engine, "probe", None)):
        raise TypeError("engine_factory_must_return_retrieval_engine_with_probe")
    return engine


def _request_from_input(payload: dict[str, Any], direction: Any | None = None) -> RetrievalRequest:
    """把 schema v1 输入转换为正式 RetrievalRequest。"""
    turns = [SimpleNamespace(speaker_id=item.get("speaker_id", "?"), text=item.get("text", "")) for item in payload.get("recent_turns", [])]
    return RetrievalRequest(
        npc_id=str(payload["npc_id"]),
        conversation_participant_ids=list(payload.get("participant_ids", [])),
        query_text=str(payload.get("query_text", "")),
        conversation_summary=str(payload.get("conversation_summary", "")),
        recent_turns=turns,
        location_id=str(payload.get("location_id", "")),
        game_time=str(payload.get("game_time_snapshot", "")),
        mode=str(payload.get("mode", "player_dialogue")),
        direction_override=direction,
        direction_source="offline_review_candidate" if direction is not None else "",
    )


def collect_records(
    candidate_path: Path,
    engine: Any | None,
    seed: int,
    query_general_llm: bool = False,
    teacher_llm: Any | None = None,
    max_samples: int = 0,
    existing_records: list[dict[str, Any]] | None = None,
    on_record: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """校准候选方向，并可选通过只读 probe 保存检索证据。"""
    resolver = DirectionResolver()
    records = list(existing_records or [])
    completed_ids = {str(item["sample_id"]) for item in records}
    candidate_ids: set[str] = set()
    new_count = 0
    for candidate in iter_jsonl(candidate_path):
        sample_id = str(candidate["sample_id"])
        if sample_id in candidate_ids:
            raise ValueError(f"duplicate_candidate_sample_id:{sample_id}")
        candidate_ids.add(sample_id)
        if sample_id in completed_ids:
            continue
        if max_samples > 0 and new_count >= max_samples:
            break
        input_payload = dict(candidate["input"])
        request = _request_from_input(input_payload)
        context = {
            "query_text": request.query_text,
            "conversation_summary": request.conversation_summary,
            "recent_turns": input_payload.get("recent_turns", []),
            "recent_memories": input_payload.get("recent_memories", []),
            "location": request.location_id,
            "game_time": request.game_time,
            "participant_ids": request.conversation_participant_ids,
        }
        if query_general_llm:
            raw_resolution = LlmDirectionProvider(
                prompt_assembler=StrictTrainingPromptAssembler(),
                llm=teacher_llm,
            ).provide(request, context)
            if raw_resolution.source != "llm":
                diagnostic = ""
                if callable(getattr(teacher_llm, "diagnostic_summary", None)):
                    diagnostic = f":{teacher_llm.diagnostic_summary()}"
                raise RuntimeError(
                    f"general_llm_teacher_failed:{candidate['sample_id']}:{raw_resolution.failure_reason}{diagnostic}"
                )
            raw_direction = direction_to_payload(raw_resolution.direction)
        else:
            raw_direction = dict(candidate["raw_direction"])
        resolution = resolver.resolve(request, context, StaticDirectionProvider(raw_direction))
        evidence = dict(candidate.get("evidence", {}))
        if engine is not None:
            result = engine.probe(_request_from_input(input_payload, resolution.direction))
            evidence["retrieved_node_ids"] = list(result.retrieved_node_ids)
            evidence["retrieval_diagnostics"] = dict(result.diagnostics)
        record = {
                "sample_id": sample_id,
                "schema_version": 1,
                "source_group": str(candidate["source_group"]),
                "split": "unassigned",
                "input": input_payload,
                "raw_direction": raw_direction,
                "calibrated_direction": direction_to_payload(resolution.direction),
                "label": direction_to_payload(resolution.direction),
                "review": {"status": "pending", "reviewer": "", "reviewed_at": ""},
                "calibration_evidence": {
                    "validation_errors": list(resolution.validation_errors),
                    "calibrations": list(resolution.calibrations),
                    "mentions": [asdict(item) for item in resolution.mentions],
                },
                "evidence": evidence,
            }
        records.append(record)
        completed_ids.add(sample_id)
        new_count += 1
        if on_record is not None:
            on_record(record)
    stale_ids = completed_ids.difference(candidate_ids)
    if max_samples == 0 and stale_ids:
        raise ValueError(f"resume_output_contains_unknown_samples:{','.join(sorted(stale_ids))}")
    return assign_grouped_splits(records, seed)


def _build_teacher_client(base_url: str, model: str, api_key_env: str) -> DiagnosticTeacherClient:
    """从指定环境变量构建独立 OpenAI-compatible 教师客户端。"""
    api_key = os.getenv(api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(f"teacher_api_key_missing:{api_key_env}")
    if not base_url.strip():
        raise ValueError("teacher_base_url_required")
    if not model.strip():
        raise ValueError("teacher_model_required")
    client = LLMClient("openai", model.strip(), api_key, base_url.strip())
    return DiagnosticTeacherClient(client, api_key)


def main() -> None:
    """解析参数并生成待人工复核 JSONL。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine-factory", default="")
    parser.add_argument("--query-general-llm", action="store_true")
    parser.add_argument("--teacher-base-url", default="")
    parser.add_argument("--teacher-model", default="")
    parser.add_argument("--teacher-api-key-env", default="MEMORY_ROUTE_TEACHER_API_KEY")
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--seed", type=int, default=20260720)
    args = parser.parse_args()
    if args.max_samples < 0:
        parser.error("--max-samples must be >= 0")
    engine = _load_engine(args.engine_factory) if args.engine_factory else None
    teacher_llm = None
    if args.query_general_llm:
        teacher_llm = _build_teacher_client(args.teacher_base_url, args.teacher_model, args.teacher_api_key_env)
    existing_records = list(iter_jsonl(args.output)) if args.resume and args.output.exists() else []
    if not args.resume:
        write_jsonl(args.output, [])
    records = collect_records(
            args.candidates,
            engine,
            args.seed,
            args.query_general_llm,
            teacher_llm,
            args.max_samples,
            existing_records,
            lambda record: append_jsonl(args.output, record),
        )
    write_jsonl(
        args.output,
        records,
    )


if __name__ == "__main__":
    main()
