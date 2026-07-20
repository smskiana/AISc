"""记忆路由训练数据契约、序列化和模型输入模板。"""

from __future__ import annotations

import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from backend.src.memory.retrieval_contracts import RetrievalDirection


DIRECTION_FIELDS = (
    "entity_mentions",
    "location_mentions",
    "themes",
    "relation_facets",
    "time_scope",
    "source_preferences",
    "recall_intent",
    "negative_directions",
    "retrieval_query",
    "query_constraints",
)

SYSTEM_PROMPT = (
    "你是记忆检索方向解析器。只输出一个 JSON 对象，不输出推理过程、回答、节点 ID 或边 ID。"
    "字段必须完整且只能是：entity_mentions:string[]，location_mentions:string[]，"
    "themes:[identity|current_location|recent_activity|relationship|cause|past_event|emotion|object|promise|general]，"
    "relation_facets:[familiarity|affinity|occupation|shared_event|impression_basis|knowledge_source]，"
    "time_scope:current|recent|past|any，source_preferences:[direct|heard|inferred]，"
    "recall_intent:locate_person|identify_entity|explain_cause|compare_relationship|recall_event|continue_reference|general_recall，"
    "negative_directions:[unrelated_player_background|unrelated_private_memory|stale_location|unrelated_person]，"
    "retrieval_query:string，query_constraints:[person_location|identity|relationship|cause|past_event|recent]。"
    "不得引入输入中不存在的人物、地点、时间或事件。"
)


def load_schema(schema_path: Path) -> dict[str, Any]:
    """读取并返回 UTF-8 JSON Schema。"""
    return json.loads(schema_path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    """逐行读取 UTF-8 JSONL，并在错误中保留行号。"""
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid_jsonl:{path}:{line_number}:{error.msg}") from error
            if not isinstance(payload, dict):
                raise ValueError(f"jsonl_record_not_object:{path}:{line_number}")
            yield payload


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    """以无 BOM UTF-8 和稳定紧凑格式写出 JSONL。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """以无 BOM UTF-8 追加单条 checkpoint 记录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def direction_from_payload(payload: dict[str, Any]) -> RetrievalDirection:
    """只从正式白名单字段构建 RetrievalDirection。"""
    values = {field: payload[field] for field in DIRECTION_FIELDS if field in payload}
    return RetrievalDirection(**values)


def direction_to_payload(direction: RetrievalDirection) -> dict[str, Any]:
    """把正式 RetrievalDirection 转为稳定训练标签。"""
    values = asdict(direction)
    return {field: values[field] for field in DIRECTION_FIELDS}


def validate_records(records: list[dict[str, Any]], schema: dict[str, Any], require_approved: bool) -> None:
    """校验 schema、审核状态、稳定 ID 泄漏和 source_group 切分。"""
    validator = Draft202012Validator(schema)
    sample_ids: set[str] = set()
    groups_by_split: dict[str, set[str]] = {}
    errors: list[str] = []
    for record in records:
        sample_id = str(record.get("sample_id", "<missing>"))
        errors.extend(f"{sample_id}:{item.message}" for item in validator.iter_errors(record))
        if sample_id in sample_ids:
            errors.append(f"duplicate_sample_id:{sample_id}")
        sample_ids.add(sample_id)
        review_status = str(record.get("review", {}).get("status", ""))
        if require_approved and review_status != "approved":
            errors.append(f"sample_not_approved:{sample_id}:{review_status}")
        label = record.get("label", {})
        forbidden = {"node_id", "node_ids", "edge_id", "edge_ids"}.intersection(label)
        if forbidden:
            errors.append(f"forbidden_label_fields:{sample_id}:{','.join(sorted(forbidden))}")
        split = str(record.get("split", "unassigned"))
        groups_by_split.setdefault(split, set()).add(str(record.get("source_group", "")))
    split_names = sorted(groups_by_split)
    for index, left in enumerate(split_names):
        for right in split_names[index + 1 :]:
            overlap = groups_by_split[left].intersection(groups_by_split[right])
            if overlap:
                errors.append(f"source_group_overlap:{left}:{right}:{','.join(sorted(overlap))}")
    if errors:
        raise ValueError("\n".join(errors))


def assign_grouped_splits(
    records: list[dict[str, Any]],
    seed: int,
    train_ratio: float = 0.8,
    validation_ratio: float = 0.1,
) -> list[dict[str, Any]]:
    """按 source_group 确定性切分，绝不拆散同源样本。"""
    groups = sorted({str(record["source_group"]) for record in records})
    random.Random(seed).shuffle(groups)
    train_count = max(1, int(len(groups) * train_ratio)) if groups else 0
    validation_count = max(1, int(len(groups) * validation_ratio)) if len(groups) >= 3 else 0
    if train_count + validation_count >= len(groups) and len(groups) >= 2:
        train_count = max(1, len(groups) - validation_count - 1)
    split_by_group: dict[str, str] = {}
    for index, group in enumerate(groups):
        split_by_group[group] = (
            "train" if index < train_count else "validation" if index < train_count + validation_count else "test"
        )
    return [{**record, "split": split_by_group[str(record["source_group"])]} for record in records]


def build_training_text(tokenizer: Any, record: dict[str, Any]) -> tuple[str, str]:
    """构建关闭 thinking 的 prompt 和仅含 assistant 标签的完整文本。"""
    user_payload = json.dumps(record["input"], ensure_ascii=False, separators=(",", ":"))
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_payload}]
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    label = json.dumps(record["label"], ensure_ascii=False, separators=(",", ":"))
    return prompt, f"{prompt}{label}{tokenizer.eos_token}"
