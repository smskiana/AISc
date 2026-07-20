"""对零样本或 Route LoRA 执行确定性字段级与检索级离线评估。"""

from __future__ import annotations

import argparse
import importlib
import json
import time
from pathlib import Path
from typing import Any

import torch
from jsonschema import Draft202012Validator
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from backend.src.memory.retrieval_contracts import DirectionResolution
from backend.src.memory.retrieval_direction import DirectionResolver
from backend.training.memory_route.collect_route_dataset import StaticDirectionProvider, _request_from_input
from backend.training.memory_route.common import build_training_text, direction_to_payload, iter_jsonl, load_schema, validate_records


def _load_engine(factory_spec: str) -> Any | None:
    """可选加载只读隔离 RetrievalEngine 工厂。"""
    if not factory_spec:
        return None
    module_name, separator, function_name = factory_spec.partition(":")
    if not separator:
        raise ValueError("engine_factory_must_be_module_colon_function")
    return getattr(importlib.import_module(module_name), function_name)()


def _parse_output(text: str) -> dict[str, Any] | None:
    """解析模型 JSON，拒绝 Markdown fence 和额外自然语言。"""
    try:
        payload = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _percentile(values: list[float], ratio: float) -> float:
    """用 nearest-rank 计算小样本也稳定的延迟分位数。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) * ratio) + 0.999999) - 1))
    return ordered[index]


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    """对固定 split 生成方向，并经正式校准链和可选 probe 计分。"""
    schema = load_schema(args.schema)
    records = list(iter_jsonl(args.dataset))
    validate_records(records, schema, require_approved=not args.allow_unreviewed_smoke)
    records = [record for record in records if record["split"] == args.split]
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, revision=args.revision)
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        revision=args.revision,
        quantization_config=quantization,
        device_map="cuda",
    )
    if args.adapter:
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()
    resolver = DirectionResolver()
    engine = _load_engine(args.engine_factory)
    output_validator = Draft202012Validator(schema["$defs"]["direction"])
    details: list[dict[str, Any]] = []
    for record in records:
        prompt, _ = build_training_text(tokenizer, record)
        inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
        started = time.perf_counter()
        generated = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False, pad_token_id=tokenizer.eos_token_id)
        latency_ms = (time.perf_counter() - started) * 1000
        text = tokenizer.decode(generated[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
        payload = _parse_output(text)
        schema_valid = payload is not None and not list(output_validator.iter_errors(payload))
        calibrated: dict[str, Any] | None = None
        retrieved_node_ids: list[str] = []
        if schema_valid and payload is not None:
            request = _request_from_input(record["input"])
            resolution: DirectionResolution = resolver.resolve(request, record["input"], StaticDirectionProvider(payload))
            calibrated = direction_to_payload(resolution.direction)
            if engine is not None:
                retrieved = engine.probe(_request_from_input(record["input"], resolution.direction))
                retrieved_node_ids = list(retrieved.retrieved_node_ids)
        expected_entities = set(record["label"]["entity_mentions"])
        actual_entities = set((calibrated or {}).get("entity_mentions", []))
        expected_nodes = set(record.get("evidence", {}).get("expected_node_ids", []))
        details.append(
            {
                "sample_id": record["sample_id"],
                "schema_valid": schema_valid,
                "entity_hits": len(expected_entities.intersection(actual_entities)),
                "entity_expected": len(expected_entities),
                "unknown_entities": sorted(actual_entities - set(record["input"].get("known_entity_aliases", [])) - expected_entities),
                "field_matches": sum((calibrated or {}).get(field) == record["label"].get(field) for field in record["label"]),
                "field_count": len(record["label"]),
                "retrieved_expected_hits": len(expected_nodes.intersection(retrieved_node_ids)),
                "retrieved_expected_count": len(expected_nodes),
                "latency_ms": round(latency_ms, 3),
                "raw_output": text[:1000],
            }
        )
    count = len(details)
    latencies = [item["latency_ms"] for item in details]
    summary = {
        "sample_count": count,
        "schema_valid_rate": sum(item["schema_valid"] for item in details) / count if count else 0.0,
        "explicit_entity_recall": sum(item["entity_hits"] for item in details) / max(1, sum(item["entity_expected"] for item in details)),
        "field_accuracy": sum(item["field_matches"] for item in details) / max(1, sum(item["field_count"] for item in details)),
        "unknown_entity_count": sum(len(item["unknown_entities"]) for item in details),
        "retrieval_hit_rate": sum(item["retrieved_expected_hits"] for item in details) / max(1, sum(item["retrieved_expected_count"] for item in details)),
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "p99": _percentile(latencies, 0.99),
            "samples": sorted(latencies),
        },
        "peak_gpu_memory_mb": round(torch.cuda.max_memory_allocated() / 1048576, 1),
        "adapter": str(args.adapter) if args.adapter else "",
        "split": args.split,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "details": details}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    """解析离线评估参数并写出结构化报告。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=Path(__file__).with_name("dataset_schema.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--engine-factory", default="")
    parser.add_argument("--split", choices=("train", "validation", "test"), default="test")
    parser.add_argument("--model-id", default="Qwen/Qwen3-0.6B")
    parser.add_argument("--revision", default="c1899de289a04d12100db370d81485cdf75e47ca")
    parser.add_argument("--max-new-tokens", type=int, default=384)
    parser.add_argument("--allow-unreviewed-smoke", action="store_true")
    args = parser.parse_args()
    print(json.dumps(evaluate(args), ensure_ascii=False))


if __name__ == "__main__":
    main()
