"""用隔离 engine factory 评估正式 provider chain 与 RetrievalEngine.probe。"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.memory.retrieval_contracts import RetrievalRequest

PROVIDER_IDS = ("r3_v2", "general_llm", "local")


def _load_factory(spec: str):
    """只接受显式 module:function，并要求工厂声明隔离数据。"""
    if ":" not in spec:
        raise ValueError("engine_factory_must_be_module_function")
    module_name, function_name = spec.split(":", 1)
    factory = getattr(importlib.import_module(module_name), function_name)
    if not getattr(factory, "aisc_isolated_retrieval_factory", False):
        raise ValueError("engine_factory_missing_isolation_declaration")
    return factory


def _read_corpus(path: Path) -> list[dict[str, Any]]:
    """读取 UTF-8 JSONL，并拒绝没有逐条隔离与权限预期的记录。"""
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid_runtime_corpus_json:{line_number}") from error
        if not isinstance(record, dict) or record.get("isolated_data") is not True or not isinstance(record.get("expected_node_ids"), list) or not isinstance(record.get("forbidden_node_ids"), list):
            raise ValueError(f"runtime_corpus_missing_isolation_or_permissions:{line_number}")
        records.append(record)
    return records


def _request(payload: dict[str, Any]) -> RetrievalRequest:
    """从 corpus 的正式字段构造检索请求，不接受策略或预算覆盖。"""
    allowed = {"npc_id", "conversation_participant_ids", "query_text", "conversation_summary", "recent_turns", "location_id", "game_time", "mode"}
    if not isinstance(payload, dict) or set(payload) - allowed or "npc_id" not in payload:
        raise ValueError("runtime_corpus_request_invalid")
    return RetrievalRequest(**payload)


def _database_snapshot(engine: Any) -> dict[str, Any]:
    """读取隔离 SQLite 的 clarity 与检索日志状态用于 probe 副作用对比。"""
    db = getattr(engine, "db", None)
    if db is None or not hasattr(db, "fetchall"):
        return {}
    edges = db.fetchall("SELECT id, clarity_ab, clarity_ba, last_traversed_ab, last_traversed_ba FROM memory_edges ORDER BY id")
    logs = db.fetchall("SELECT id FROM memory_retrieval_logs ORDER BY id")
    return {"edges": edges, "retrieval_log_ids": [str(item["id"]) for item in logs]}


def evaluate(factory_spec: str, corpus_path: Path, output_path: Path, provider_id: str) -> dict[str, Any]:
    """逐条调用只读 probe，并写出命中、权限和安全诊断证据。"""
    if provider_id not in PROVIDER_IDS:
        raise ValueError("unsupported_direction_provider")
    engine = _load_factory(factory_spec)(provider_id)
    if not hasattr(engine, "probe"):
        raise ValueError("engine_factory_result_missing_probe")
    runtime = getattr(engine, "direction_provider_runtime", None)
    started = time.perf_counter()
    warmup = runtime.warmup() if runtime is not None else {}
    before = _database_snapshot(engine)
    details: list[dict[str, Any]] = []
    try:
        for record in _read_corpus(corpus_path):
            case_started = time.perf_counter()
            result = engine.probe(_request(record.get("request", {})))
            actual = set(result.retrieved_node_ids)
            expected = set(str(item) for item in record["expected_node_ids"])
            forbidden = set(str(item) for item in record["forbidden_node_ids"])
            details.append({"case_id": str(record.get("case_id", "")), "expected_hits": sorted(expected & actual), "expected_count": len(expected), "forbidden_hits": sorted(forbidden & actual), "retrieved_node_ids": sorted(actual), "direction_provider_requested": result.diagnostics.get("direction_provider_requested"), "direction_provider_adopted": result.diagnostics.get("direction_provider_adopted"), "direction_fallback_reasons": result.diagnostics.get("direction_fallback_reasons", []), "direction_model_call_count": result.diagnostics.get("direction_model_call_count", 0), "vector_query_count": result.diagnostics.get("vector_query_count", 0), "llm_route_calls": result.diagnostics.get("llm_route_calls", 0), "elapsed_ms": round((time.perf_counter() - case_started) * 1000, 3)})
        after = _database_snapshot(engine)
    finally:
        if runtime is not None:
            runtime.close()
    expected_total = sum(item["expected_count"] for item in details)
    report = {"summary": {"provider_id": provider_id, "case_count": len(details), "expected_hit_rate": sum(len(item["expected_hits"]) for item in details) / max(1, expected_total), "forbidden_hit_count": sum(len(item["forbidden_hits"]) for item in details), "adopted_provider_count": sum(item["direction_provider_adopted"] == provider_id for item in details), "side_effect_free": before == after, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "warmup": warmup}, "details": details, "side_effect_snapshot": {"before": before, "after": after}}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report["summary"]


def main() -> None:
    """解析显式隔离工厂与 corpus 参数。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-factory", required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", choices=PROVIDER_IDS, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.engine_factory, args.corpus, args.output, args.provider), ensure_ascii=False))


if __name__ == "__main__":
    main()
