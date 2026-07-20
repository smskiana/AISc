import json
from pathlib import Path

import pytest

from backend.src.memory.retrieval_contracts import (
    NegativeDirection,
    QueryConstraint,
    RecallIntent,
    RelationFacet,
    SourcePreference,
    Theme,
    TimeScope,
)
from backend.training.memory_route.collect_route_dataset import (
    DiagnosticTeacherClient,
    StrictTrainingPromptAssembler,
    collect_records,
)
from backend.training.memory_route.generate_synthetic_candidates import (
    build_stratified_sample,
    build_summary,
    generate_candidates,
    normalize_input,
    validate_batch,
)
from backend.training.memory_route.common import (
    assign_grouped_splits,
    append_jsonl,
    direction_from_payload,
    direction_to_payload,
    iter_jsonl,
    load_schema,
    validate_records,
    write_jsonl,
)


SCHEMA = Path(__file__).parents[1] / "training" / "memory_route" / "dataset_schema.json"
TRAINING_REQUIREMENTS = Path(__file__).parents[1] / "training" / "memory_route" / "requirements-lock.txt"


def _record(sample_id: str, source_group: str, split: str = "train", status: str = "approved") -> dict:
    """构建最小合法的脱敏训练样本。"""
    direction = {
        "entity_mentions": ["千早"],
        "location_mentions": [],
        "themes": ["current_location"],
        "relation_facets": [],
        "time_scope": "recent",
        "source_preferences": [],
        "recall_intent": "locate_person",
        "negative_directions": ["stale_location"],
        "retrieval_query": "千早现在在哪里",
        "query_constraints": ["person_location", "recent"],
    }
    return {
        "sample_id": sample_id,
        "schema_version": 1,
        "source_group": source_group,
        "split": split,
        "input": {
            "schema_version": 1,
            "npc_id": "sakura",
            "query_text": "千早现在在哪里？",
            "conversation_summary": "",
            "recent_turns": [],
            "recent_memories": [],
            "location_id": "flower_shop.counter",
            "location_display_text": "花店柜台",
            "game_time_snapshot": "Day 4 09:38",
            "participant_ids": ["player"],
            "known_entity_aliases": ["千早"],
            "mode": "player_dialogue",
        },
        "raw_direction": dict(direction),
        "calibrated_direction": dict(direction),
        "label": dict(direction),
        "review": {"status": status, "reviewer": "reviewer", "reviewed_at": "2026-07-20T00:00:00+08:00"},
        "calibration_evidence": {},
        "evidence": {},
    }


def test_schema_utf8_round_trip_and_direction_whitelist(tmp_path: Path) -> None:
    """中文 JSONL 往返后仍满足 schema 与正式方向字段。"""
    path = tmp_path / "route.jsonl"
    write_jsonl(path, [_record("sample-1", "story-a")])
    records = list(iter_jsonl(path))
    validate_records(records, load_schema(SCHEMA), require_approved=True)
    assert records[0]["input"]["query_text"] == "千早现在在哪里？"
    assert direction_to_payload(direction_from_payload(records[0]["label"])) == records[0]["label"]


def test_training_lock_includes_collector_runtime_dependencies() -> None:
    """独立训练环境必须声明教师采集器直接导入的 OpenAI SDK。"""
    requirements = TRAINING_REQUIREMENTS.read_text(encoding="utf-8").splitlines()
    assert "openai==2.43.0" in requirements


def test_validation_rejects_unreviewed_and_forbidden_label_ids() -> None:
    """正式训练拒绝未审核样本和模型标签中的图稳定 ID。"""
    record = _record("sample-1", "story-a", status="pending")
    record["label"]["node_ids"] = ["secret-node"]
    with pytest.raises(ValueError) as error:
        validate_records([record], load_schema(SCHEMA), require_approved=True)
    assert "sample_not_approved" in str(error.value)
    assert "forbidden_label_fields" in str(error.value)


def test_group_split_is_deterministic_and_has_no_overlap() -> None:
    """相同 source_group 永远进入同一 split。"""
    records = [_record(f"sample-{index}", f"story-{index // 2}", split="unassigned") for index in range(10)]
    first = assign_grouped_splits(records, seed=7)
    second = assign_grouped_splits(records, seed=7)
    assert [item["split"] for item in first] == [item["split"] for item in second]
    by_group: dict[str, set[str]] = {}
    for item in first:
        by_group.setdefault(item["source_group"], set()).add(item["split"])
    assert all(len(splits) == 1 for splits in by_group.values())
    validate_records(first, load_schema(SCHEMA), require_approved=True)


def test_schema_enums_match_runtime_contract() -> None:
    """训练 schema 枚举必须与正式 RetrievalDirection 白名单完全一致。"""
    direction = load_schema(SCHEMA)["$defs"]["direction"]["properties"]
    expected = {
        "themes": {item.value for item in Theme},
        "relation_facets": {item.value for item in RelationFacet},
        "time_scope": {item.value for item in TimeScope},
        "source_preferences": {item.value for item in SourcePreference},
        "recall_intent": {item.value for item in RecallIntent},
        "negative_directions": {item.value for item in NegativeDirection},
        "query_constraints": {item.value for item in QueryConstraint},
    }
    for field, values in expected.items():
        schema_values = direction[field]["enum"] if "enum" in direction[field] else direction[field]["items"]["enum"]
        assert set(schema_values) == values


def test_collector_uses_formal_direction_calibration(tmp_path: Path) -> None:
    """采集候选必须经过正式 resolver 修正明确定位问句。"""
    candidate = {
        "sample_id": "candidate-1",
        "source_group": "story-a",
        "input": _record("source", "story-a")["input"],
        "raw_direction": {
            **_record("source", "story-a")["raw_direction"],
            "themes": ["general"],
            "recall_intent": "general_recall",
            "query_constraints": [],
        },
        "evidence": {},
    }
    path = tmp_path / "candidates.jsonl"
    write_jsonl(path, [candidate])
    [record] = collect_records(path, engine=None, seed=7)
    assert record["label"]["recall_intent"] == "locate_person"
    assert record["label"]["themes"] == ["current_location"]
    assert "person_location" in record["label"]["query_constraints"]
    assert record["review"]["status"] == "pending"


class _TeacherLlm:
    """返回固定错误方向，用于验证显式教师注入和本地校准。"""

    is_available = True

    def __init__(self) -> None:
        """初始化调用计数。"""
        self.call_count = 0

    def chat(self, messages: list[dict], **kwargs: object) -> str:
        """返回可解析但需要正式 resolver 修正的教师 JSON。"""
        self.call_count += 1
        direction = _record("source", "story-a")["raw_direction"]
        direction["themes"] = ["general"]
        direction["recall_intent"] = "general_recall"
        direction["query_constraints"] = []
        return json.dumps(direction, ensure_ascii=False)


def test_collector_queries_injected_teacher_with_sample_limit(tmp_path: Path) -> None:
    """离线采集可显式调用教师模型，并在费用上限前停止。"""
    candidates = []
    for index in range(2):
        candidates.append(
            {
                "sample_id": f"candidate-{index}",
                "source_group": f"story-{index}",
                "input": _record("source", f"story-{index}")["input"],
                "raw_direction": _record("source", f"story-{index}")["raw_direction"],
                "evidence": {},
            }
        )
    path = tmp_path / "candidates.jsonl"
    write_jsonl(path, candidates)
    teacher = _TeacherLlm()

    records = collect_records(path, None, seed=7, query_general_llm=True, teacher_llm=teacher, max_samples=1)

    assert teacher.call_count == 1
    assert len(records) == 1
    assert records[0]["raw_direction"]["recall_intent"] == "general_recall"
    assert records[0]["label"]["recall_intent"] == "locate_person"


def test_training_teacher_prompt_contains_exact_direction_whitelist() -> None:
    """离线教师必须同时收到正式上下文 Prompt 和完整训练枚举白名单。"""
    messages = StrictTrainingPromptAssembler().build("memory_direction", {"query_text": "千早在哪里？"})

    assert messages[0]["role"] == "system"
    assert "locate_person|identify_entity|explain_cause" in messages[0]["content"]
    assert "current_location|recent_activity|relationship" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "千早在哪里？" in messages[1]["content"]


class _FailingLlmClient:
    """模拟包含敏感凭据的外部服务异常。"""

    is_available = True

    def chat(self, messages: list[dict], **kwargs: object) -> str:
        """抛出带测试密钥的鉴权异常。"""
        raise RuntimeError("401 invalid key test-secret")


def test_collector_reports_redacted_teacher_error(tmp_path: Path) -> None:
    """教师失败应保留服务端原因，同时不得把 API Key 写入错误。"""
    candidate = {
        "sample_id": "candidate-1",
        "source_group": "story-a",
        "input": _record("source", "story-a")["input"],
        "raw_direction": _record("source", "story-a")["raw_direction"],
        "evidence": {},
    }
    path = tmp_path / "candidates.jsonl"
    write_jsonl(path, [candidate])
    teacher = DiagnosticTeacherClient(_FailingLlmClient(), "test-secret")

    with pytest.raises(RuntimeError) as error:
        collect_records(path, None, seed=7, query_general_llm=True, teacher_llm=teacher, max_samples=1)

    assert "401 invalid key <redacted>" in str(error.value)
    assert "test-secret" not in str(error.value)


def test_synthetic_candidates_are_deterministic_balanced_and_desensitized() -> None:
    """合成候选应覆盖全部类别、稳定复现且不携带真实会话标记。"""
    first = generate_candidates(96, seed=7)
    second = generate_candidates(96, seed=7)

    assert first == second
    assert len({item["sample_id"] for item in first}) == 96
    assert len({item["evidence"]["synthetic_category"] for item in first}) == 24
    assert all(item["evidence"]["synthetic"] is True for item in first)
    assert all(item["evidence"]["contains_real_session_data"] is False for item in first)
    assert all(item["source_group"].startswith("synthetic_") for item in first)
    assert all(direction_from_payload(item["raw_direction"]) for item in first)
    reference_rows = [item for item in first if item["evidence"]["synthetic_category"] == "cross_turn_reference"]
    for item in reference_rows:
        target_name = item["input"]["known_entity_aliases"][0]
        pronoun = item["input"]["known_entity_aliases"][1]
        assert pronoun in item["input"]["query_text"]
        assert target_name in item["input"]["recent_turns"][0]["text"]
        assert pronoun in item["input"]["recent_turns"][0]["text"]
    summary = build_summary(first, seed=7)
    assert summary["sample_count"] == 96
    assert summary["source_group_count"] >= 24
    assert set(summary["modes"]) == {"npc_dialogue", "player_dialogue"}


def test_expanded_candidate_batch_has_no_old_or_internal_conflicts() -> None:
    """扩展批次必须使用独立前缀，且规范化输入与旧批次完全不重复。"""
    old_records = generate_candidates(96, seed=7)
    new_records = generate_candidates(384, seed=11, batch_prefix="synthetic-b02", start_index=97)

    checks = validate_batch(new_records, old_records)

    assert all(value == 0 for value in checks.values())
    assert len({normalize_input(item["input"]) for item in new_records}) == 384
    assert len(build_stratified_sample(new_records, seed=11)) == 24
    assert all(item["sample_id"].startswith("synthetic-b02-") for item in new_records)
    assert all(item["source_group"].startswith("synthetic-b02_") for item in new_records)


def test_collector_checkpoints_and_resumes_missing_samples(tmp_path: Path) -> None:
    """批量教师采集应逐条落盘，续跑时只调用缺失样本。"""
    candidates = []
    for index in range(3):
        candidates.append(
            {
                "sample_id": f"candidate-{index}",
                "source_group": f"story-{index}",
                "input": _record("source", f"story-{index}")["input"],
                "raw_direction": _record("source", f"story-{index}")["raw_direction"],
                "evidence": {},
            }
        )
    candidate_path = tmp_path / "candidates.jsonl"
    output_path = tmp_path / "pending.jsonl"
    write_jsonl(candidate_path, candidates)
    teacher = _TeacherLlm()

    partial = collect_records(
        candidate_path,
        None,
        seed=7,
        query_general_llm=True,
        teacher_llm=teacher,
        max_samples=1,
        on_record=lambda record: append_jsonl(output_path, record),
    )
    completed = collect_records(
        candidate_path,
        None,
        seed=7,
        query_general_llm=True,
        teacher_llm=teacher,
        existing_records=list(iter_jsonl(output_path)),
        on_record=lambda record: append_jsonl(output_path, record),
    )

    assert len(partial) == 1
    assert len(completed) == 3
    assert teacher.call_count == 3
    assert len(list(iter_jsonl(output_path))) == 3
