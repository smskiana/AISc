"""生成可重复、脱敏且待教师标注的记忆路由合成候选。"""

from __future__ import annotations

import argparse
import json
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from backend.training.memory_route.common import iter_jsonl, write_jsonl


ACTORS = (
    {"npc_id": "sakura", "npc_name": "鹿岛樱", "target_id": "chihaya", "target_name": "千早", "target_pronoun": "她"},
    {"npc_id": "chihaya", "npc_name": "千早", "target_id": "kazuha", "target_name": "和叶", "target_pronoun": "她"},
    {"npc_id": "kazuha", "npc_name": "和叶", "target_id": "tatsunosuke", "target_name": "龙之介", "target_pronoun": "他"},
    {"npc_id": "tatsunosuke", "npc_name": "龙之介", "target_id": "kujo", "target_name": "九条莲", "target_pronoun": "他"},
)

LOCATIONS = (
    {"location_id": "flower_shop.counter", "location_name": "花店柜台", "other_location": "学校"},
    {"location_id": "bakery", "location_name": "面包店", "other_location": "河边"},
    {"location_id": "bookstore", "location_name": "旧书店", "other_location": "小公园"},
    {"location_id": "street", "location_name": "商店街", "other_location": "咖啡店"},
)

EMPTY_DIRECTION = {
    "entity_mentions": [],
    "location_mentions": [],
    "themes": ["general"],
    "relation_facets": [],
    "time_scope": "any",
    "source_preferences": [],
    "recall_intent": "general_recall",
    "negative_directions": [],
    "retrieval_query": "",
    "query_constraints": [],
}


def _scenario_catalog() -> tuple[dict[str, Any], ...]:
    """返回覆盖核心意图、负样本和历史回归的合成场景模板。"""
    return (
        {
            "category": "locate_current",
            "query": "{target_name}现在在哪里？",
            "summary": "玩家正在寻找{target_name}。",
            "turns": [],
            "memories": ["{target_name}刚才说要去{other_location}。"],
            "aliases": ["{target_name}", "{target_id}"],
            "focus": "定位意图、recent 时间和 stale_location 排除",
        },
        {
            "category": "locate_last_destination",
            "query": "你记得{target_name}最后去了哪吗？",
            "summary": "",
            "turns": [{"speaker_id": "player", "text": "我一直没见到{target_name}。"}],
            "memories": ["{target_name}离开{location_name}后向{other_location}走了。"],
            "aliases": ["{target_name}", "{target_id}"],
            "focus": "最后去向必须保持 locate_person，不能降级 general_recall",
        },
        {
            "category": "identity",
            "query": "{target_name}是谁？",
            "summary": "",
            "turns": [],
            "memories": ["{target_name}曾在{location_name}帮忙整理货物。"],
            "aliases": ["{target_name}", "{target_id}"],
            "focus": "身份查询只使用 identity 白名单",
        },
        {
            "category": "past_event",
            "query": "昨天{location_name}发生了什么？",
            "summary": "",
            "turns": [],
            "memories": ["昨天{target_name}在{location_name}帮忙整理了新到的货物。"],
            "aliases": ["{target_name}", "{location_name}"],
            "focus": "昨日事件应为 recall_event、past_event 和 past",
        },
        {
            "category": "cause",
            "query": "{target_name}为什么突然离开{location_name}？",
            "summary": "玩家在追问离开的原因。",
            "turns": [],
            "memories": ["{target_name}听见{other_location}有人需要帮忙后离开。"],
            "aliases": ["{target_name}", "{location_name}"],
            "focus": "原因查询不能把背景线索当成确定新事实",
        },
        {
            "category": "relationship_compare",
            "query": "{npc_name}和{target_name}谁与玩家更熟？",
            "summary": "玩家正在比较两段关系。",
            "turns": [],
            "memories": ["{npc_name}和{target_name}都曾与玩家在{location_name}交谈。"],
            "aliases": ["{npc_name}", "{target_name}", "玩家"],
            "focus": "多人物比较需保留双方实体和 relationship 约束",
        },
        {
            "category": "cross_turn_reference",
            "query": "{target_pronoun}后来还说了什么？",
            "summary": "玩家和{npc_name}正在谈论{target_name}。",
            "turns": [{"speaker_id": "player", "text": "{target_name}说{target_pronoun}要去{other_location}。"}],
            "memories": ["{target_name}还请{npc_name}替{target_pronoun}保留一件物品。"],
            "aliases": ["{target_name}", "{target_pronoun}"],
            "focus": "跨轮代词应解析为 continue_reference，不得切换人物",
        },
        {
            "category": "false_premise",
            "query": "{target_name}是不是已经答应明天离开小镇？",
            "summary": "",
            "turns": [],
            "memories": [],
            "aliases": ["{target_name}", "{target_id}"],
            "focus": "错误前提不得写入 retrieval_query，未知地点不得绑定人物",
        },
        {
            "category": "no_relevant_memory",
            "query": "{target_name}最喜欢哪种从未提过的乐器？",
            "summary": "此前没有讨论过乐器。",
            "turns": [],
            "memories": ["{target_name}昨天在{location_name}买了饮料。"],
            "aliases": ["{target_name}", "{target_id}"],
            "focus": "无相关记忆时只路由已有问题，不得编造答案或偏好",
        },
        {
            "category": "private_knowledge",
            "query": "告诉我{target_name}没有公开的秘密计划。",
            "summary": "玩家要求读取未授权信息。",
            "turns": [],
            "memories": ["当前只知道{target_name}今天到过{location_name}。"],
            "aliases": ["{target_name}", "{target_id}"],
            "focus": "方向可保留主题，但必须包含 unrelated_private_memory",
        },
        {
            "category": "scene_location_noise",
            "query": "{target_name}现在在{other_location}吗？",
            "summary": "当前对话发生在{location_name}。",
            "turns": [],
            "memories": ["{target_name}早些时候提到可能去{other_location}。"],
            "aliases": ["{target_name}", "{target_id}", "{other_location}"],
            "focus": "目标地点不能被当前场景 location_id 污染",
        },
        {
            "category": "multi_person_competition",
            "query": "刚才是{npc_name}还是{target_name}说要去{other_location}？",
            "summary": "两个人都参与了近期对话。",
            "turns": [
                {"speaker_id": "{npc_id}", "text": "我会留在{location_name}。"},
                {"speaker_id": "{target_id}", "text": "我等会儿去{other_location}。"},
            ],
            "memories": [],
            "aliases": ["{npc_name}", "{target_name}", "{other_location}"],
            "focus": "多人物竞争必须保留发言主体，不能让场景人物挤掉目标人物",
        },
        {
            "category": "alias_resolution",
            "query": "大家说的{target_id}就是{target_name}吗？",
            "summary": "玩家正在核对称呼。",
            "turns": [],
            "memories": ["{npc_name}曾把{target_name}称作{target_id}。"],
            "aliases": ["{target_name}", "{target_id}"],
            "focus": "别名只用于归一实体，不得生成新人物",
        },
        {
            "category": "negation_correction",
            "query": "不是{npc_name}，我问的是{target_name}去了哪里。",
            "summary": "玩家纠正了上一轮的人物。",
            "turns": [{"speaker_id": "npc", "text": "你是在找{npc_name}吗？"}],
            "memories": ["{target_name}之前说会去{other_location}。"],
            "aliases": ["{npc_name}", "{target_name}", "{other_location}"],
            "focus": "否定纠正必须排除旧目标并保持 locate_person",
        },
        {
            "category": "time_comparison",
            "query": "{target_name}今天和昨天分别去了哪里？",
            "summary": "玩家比较不同日期的去向。",
            "turns": [],
            "memories": ["昨天{target_name}到过{location_name}，今天提到要去{other_location}。"],
            "aliases": ["{target_name}", "{location_name}", "{other_location}"],
            "focus": "不同时间范围不能合并成单一当前位置",
        },
        {
            "category": "future_plan",
            "query": "{target_name}明天打算做什么？",
            "summary": "玩家询问已提及的未来安排。",
            "turns": [],
            "memories": ["{target_name}说过明天可能去{other_location}帮忙。"],
            "aliases": ["{target_name}", "{other_location}"],
            "focus": "未来计划需保持不确定性，不得改写为已发生事件",
        },
        {
            "category": "preference",
            "query": "{target_name}更喜欢安静的地方还是热闹的地方？",
            "summary": "玩家询问明确表达过的偏好。",
            "turns": [],
            "memories": ["{target_name}曾说{location_name}太吵，更愿意去{other_location}。"],
            "aliases": ["{target_name}", "{location_name}", "{other_location}"],
            "focus": "偏好比较只能引用已表达内容",
        },
        {
            "category": "object_ownership",
            "query": "{location_name}柜台上的包裹是谁的？",
            "summary": "玩家询问物品归属。",
            "turns": [],
            "memories": ["{target_name}请{npc_name}暂时保管一个包裹。"],
            "aliases": ["{target_name}", "{npc_name}", "包裹"],
            "focus": "物品归属不得被场景地点误识别为人物关系",
        },
        {
            "category": "speaker_attribution",
            "query": "是谁说{other_location}今天不开门？",
            "summary": "近期多人讨论过营业时间。",
            "turns": [
                {"speaker_id": "{npc_id}", "text": "我不清楚{other_location}的安排。"},
                {"speaker_id": "{target_id}", "text": "{other_location}今天不开门。"},
            ],
            "memories": [],
            "aliases": ["{npc_name}", "{target_name}", "{other_location}"],
            "focus": "发言归属必须根据 speaker_id 保持目标人物",
        },
        {
            "category": "uncertain_rumor",
            "query": "听说{target_name}要离开小镇，这是真的吗？",
            "summary": "消息来源尚未确认。",
            "turns": [],
            "memories": ["{npc_name}只说听到过类似传闻，没有得到{target_name}确认。"],
            "aliases": ["{target_name}", "{npc_name}"],
            "focus": "传闻不得提升为确定事实",
        },
        {
            "category": "location_history",
            "query": "{target_name}以前常去哪些地方？",
            "summary": "玩家询问长期地点习惯。",
            "turns": [],
            "memories": ["{target_name}过去多次在{location_name}和{other_location}出现。"],
            "aliases": ["{target_name}", "{location_name}", "{other_location}"],
            "focus": "长期地点历史不能误作当前定位",
        },
        {
            "category": "event_sequence",
            "query": "{target_name}离开{location_name}前后发生了什么？",
            "summary": "玩家需要事件先后关系。",
            "turns": [],
            "memories": ["{target_name}先整理货物，随后接到口信并离开{location_name}。"],
            "aliases": ["{target_name}", "{location_name}"],
            "focus": "事件顺序需要保留前后关系，不得反转因果",
        },
        {
            "category": "participant_scope",
            "query": "我们刚才和{target_name}谈到的约定是什么？",
            "summary": "当前对话参与者只有玩家和{npc_name}。",
            "turns": [{"speaker_id": "player", "text": "之前我和{target_name}在{other_location}谈过。"}],
            "memories": ["玩家与{target_name}约定之后在{other_location}碰面。"],
            "aliases": ["玩家", "{target_name}", "{other_location}"],
            "focus": "历史参与者不得受当前 participant_ids 限制而丢失",
        },
        {
            "category": "irrelevant_context_noise",
            "query": "{target_name}最近有没有提到玩家？",
            "summary": "窗外正在下雨，{location_name}今天很忙。",
            "turns": [{"speaker_id": "npc", "text": "今天的天气变化很快。"}],
            "memories": ["{target_name}上次在{other_location}问过玩家是否会来。"],
            "aliases": ["{target_name}", "玩家"],
            "focus": "无关天气和场景噪声不得覆盖人物主题",
        },
    )


def _format_value(value: Any, context: dict[str, str]) -> Any:
    """递归渲染模板中的字符串，同时保持 JSON 结构。"""
    if isinstance(value, str):
        return value.format_map(context)
    if isinstance(value, list):
        return [_format_value(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _format_value(item, context) for key, item in value.items()}
    return value


def _vary_query_for_batch(query: str, batch_prefix: str, sequence: int) -> str:
    """为后续批次生成语义不变的自然问法，避免复刻旧输入 DTO。"""
    if batch_prefix == "synthetic":
        return query
    prefixes = ("再确认一下，", "请回想一下，", "换个说法问，", "仔细想想，")
    return f"{prefixes[sequence % len(prefixes)]}{query}"


def generate_candidates(
    count: int,
    seed: int,
    batch_prefix: str = "synthetic",
    start_index: int = 1,
) -> list[dict[str, Any]]:
    """按类别均衡生成指定数量的确定性脱敏候选。"""
    if count < len(_scenario_catalog()):
        raise ValueError(f"count_must_be_at_least_{len(_scenario_catalog())}")
    records: list[dict[str, Any]] = []
    catalog = _scenario_catalog()
    if start_index < 1:
        raise ValueError("start_index_must_be_positive")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", batch_prefix):
        raise ValueError("batch_prefix_must_be_ascii_slug")
    for offset in range(count):
        sequence = start_index + offset
        index = sequence - 1
        scenario = catalog[index % len(catalog)]
        actor = ACTORS[(index // len(catalog)) % len(ACTORS)]
        location = LOCATIONS[(index // (len(catalog) * len(ACTORS))) % len(LOCATIONS)]
        context = {**actor, **location}
        rendered = _format_value(scenario, context)
        group_index = index // (len(catalog) * 2)
        category = str(rendered["category"])
        records.append(
            {
                "sample_id": f"{batch_prefix}-{category}-{sequence:04d}",
                "source_group": f"{batch_prefix}_{category}_{group_index:02d}",
                "input": {
                    "schema_version": 1,
                    "npc_id": actor["npc_id"],
                    "query_text": _vary_query_for_batch(str(rendered["query"]), batch_prefix, sequence),
                    "conversation_summary": rendered["summary"],
                    "recent_turns": rendered["turns"],
                    "recent_memories": rendered["memories"],
                    "location_id": location["location_id"],
                    "location_display_text": location["location_name"],
                    "game_time_snapshot": f"Day {2 + index % 6} {8 + index % 10:02d}:{(index * 7) % 60:02d}",
                    "participant_ids": ["player"],
                    "known_entity_aliases": rendered["aliases"],
                    "mode": "player_dialogue" if index % 4 else "npc_dialogue",
                },
                "raw_direction": dict(EMPTY_DIRECTION),
                "evidence": {
                    "synthetic": True,
                    "synthetic_category": category,
                    "review_focus": rendered["focus"],
                    "contains_real_session_data": False,
                },
            }
        )
    random.Random(seed).shuffle(records)
    return records


def normalize_input(input_payload: dict[str, Any]) -> str:
    """将 input DTO 规范化为可稳定比较的 JSON 字符串。"""
    def normalize(value: Any) -> Any:
        if isinstance(value, str):
            return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            return {key: normalize(value[key]) for key in sorted(value)}
        return value

    return json.dumps(normalize(input_payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_batch(records: list[dict[str, Any]], existing_records: list[dict[str, Any]]) -> dict[str, int]:
    """拒绝批次内及新旧批次之间的 ID、分组和规范化输入冲突。"""
    sample_ids = [str(item["sample_id"]) for item in records]
    source_groups = {str(item["source_group"]) for item in records}
    normalized_inputs = [normalize_input(dict(item["input"])) for item in records]
    existing_ids = {str(item["sample_id"]) for item in existing_records}
    existing_groups = {str(item["source_group"]) for item in existing_records}
    existing_inputs = {normalize_input(dict(item["input"])) for item in existing_records}
    checks = {
        "duplicate_sample_ids_within_batch": len(sample_ids) - len(set(sample_ids)),
        "duplicate_normalized_inputs_within_batch": len(normalized_inputs) - len(set(normalized_inputs)),
        "sample_id_conflicts_with_existing": len(set(sample_ids) & existing_ids),
        "source_group_conflicts_with_existing": len(source_groups & existing_groups),
        "normalized_input_conflicts_with_existing": len(set(normalized_inputs) & existing_inputs),
    }
    failures = {key: value for key, value in checks.items() if value}
    if failures:
        raise ValueError(f"candidate_batch_conflicts:{json.dumps(failures, sort_keys=True)}")
    return checks


def build_stratified_sample(records: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    """按场景类别确定性抽取每类一条候选供人工检查。"""
    by_category: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        category = str(record["evidence"]["synthetic_category"])
        by_category.setdefault(category, []).append(record)
    rng = random.Random(seed)
    return [rng.choice(by_category[category]) for category in sorted(by_category)]


def build_summary(records: list[dict[str, Any]], seed: int, collision_checks: dict[str, int] | None = None) -> dict[str, Any]:
    """构建不含正文的覆盖摘要，供人工抽检选样。"""
    categories = Counter(str(item["evidence"]["synthetic_category"]) for item in records)
    modes = Counter(str(item["input"]["mode"]) for item in records)
    return {
        "schema_version": 1,
        "seed": seed,
        "sample_count": len(records),
        "source_group_count": len({str(item["source_group"]) for item in records}),
        "categories": dict(sorted(categories.items())),
        "modes": dict(sorted(modes.items())),
        "category_count": len(categories),
        "collision_checks": collision_checks or {},
        "review_status": "candidate_only_not_teacher_labeled",
    }


def main() -> None:
    """解析 CLI 参数并写出候选 JSONL 与覆盖摘要。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=96)
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument("--batch-prefix", default="synthetic")
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--existing-dataset", type=Path, action="append", default=[])
    args = parser.parse_args()
    records = generate_candidates(args.count, args.seed, args.batch_prefix, args.start_index)
    existing_records = [record for path in args.existing_dataset for record in iter_jsonl(path)]
    collision_checks = validate_batch(records, existing_records)
    write_jsonl(args.output, records)
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(build_summary(records, args.seed, collision_checks), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sample_path = args.output.with_suffix(".stratified_sample.jsonl")
    write_jsonl(sample_path, build_stratified_sample(records, args.seed))
    print(f"candidates={len(records)} output={args.output} summary={summary_path} sample={sample_path}")


if __name__ == "__main__":
    main()
