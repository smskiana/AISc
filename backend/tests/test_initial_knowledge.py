"""初始知识配置与观察者投影的纯规则测试。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.src.memory.initial_knowledge import (
    KnowledgeRelationshipContext,
    KnowledgeScope,
    load_initial_knowledge,
    project_initial_knowledge,
)


KNOWN_IDS = {"player", "sakura", "chihaya", "kazuha", "tatsunosuke", "kujo"}


def _fact(**overrides: object) -> dict:
    """构造测试用的最小稳定事实配置。"""
    value = {
        "fact_id": "bakery_identity",
        "fact_type": "identity",
        "subject_ids": ["chihaya"],
        "location_ids": ["shopping_street"],
        "canonical_summary": "千早经营面包店「小麦色」",
        "knowledge_scope": "public",
        "knower_ids": [],
        "participant_ids": [],
        "excluded_observer_ids": [],
        "source_type": "public_record",
        "confidence": 0.98,
        "importance": 0.82,
        "created_day": 0,
        "projections": {
            "default": "大家都知道，{canonical_summary}。",
        },
    }
    value.update(overrides)
    return value


class InitialKnowledgeRulesTests(unittest.TestCase):
    """验证五种知识范围、模板选择和稳定标识。"""

    def _load(self, facts: list[dict]) -> tuple:
        """将内存事实写入临时配置并通过正式校验入口读取。"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "initial_knowledge.json"
            path.write_text(
                json.dumps({"schema_version": 1, "facts": facts}, ensure_ascii=False),
                encoding="utf-8",
            )
            return load_initial_knowledge(path, known_ids=KNOWN_IDS)

    def test_public_community_participant_explicit_and_private_visibility(self) -> None:
        """不同 scope 应由统一规则决定可见性，私密事实不得泄露。"""
        facts = [
            _fact(fact_id="public_fact"),
            _fact(
                fact_id="community_fact",
                knowledge_scope="community",
                projections={"default": "街坊知道，{canonical_summary}。"},
            ),
            _fact(
                fact_id="participant_fact",
                knowledge_scope="participants",
                participant_ids=["sakura"],
                projections={"participant": "樱亲身经历过：{canonical_summary}。"},
            ),
            _fact(
                fact_id="explicit_fact",
                knowledge_scope="explicit_knowers",
                knower_ids=["kazuha"],
                projections={"explicit_knower": "和叶被明确告知：{canonical_summary}。"},
            ),
            _fact(
                fact_id="private_fact",
                fact_type="secret",
                knowledge_scope="private",
                knower_ids=["kujo"],
                projections={
                    "subject": "这是{observer_id}亲身知道的：{canonical_summary}。",
                    "explicit_knower": "九条被告知：{canonical_summary}。",
                },
            ),
        ]
        loaded = self._load(facts)
        context = KnowledgeRelationshipContext(community_observer_ids=frozenset(KNOWN_IDS))

        sakura = project_initial_knowledge(loaded, "sakura", context)
        self.assertEqual(
            {item.source_fact_id for item in sakura.projections},
            {"public_fact", "community_fact", "participant_fact"},
        )
        self.assertIn("participant", {item.visibility_rule for item in sakura.projections})
        self.assertEqual(
            {item.fact_id for item in sakura.excluded},
            {"explicit_fact", "private_fact"},
        )

        kujo = project_initial_knowledge(loaded, "kujo", context)
        private = next(item for item in kujo.projections if item.source_fact_id == "private_fact")
        self.assertEqual(private.visibility_rule, "explicit_knower")

    def test_rumor_keeps_uncertain_template_and_projection_id_is_stable(self) -> None:
        """传闻必须使用不确定文本，projection ID 不受运行顺序影响。"""
        facts = [
            _fact(
                fact_id="cafe_rumor",
                fact_type="rumor",
                source_type="community_gossip",
                projections={"rumor": "听说{canonical_summary}，但还没人确认。"},
            )
        ]
        loaded = self._load(facts)
        context = KnowledgeRelationshipContext(community_observer_ids=frozenset(KNOWN_IDS))

        first = project_initial_knowledge(loaded, "sakura", context)
        second = project_initial_knowledge(tuple(reversed(loaded)), "sakura", context)

        self.assertEqual(first.projections[0].projection_id, "initial_knowledge__sakura__cafe_rumor")
        self.assertEqual(first.projections[0].projection_id, second.projections[0].projection_id)
        self.assertIn("听说", first.projections[0].value)

    def test_excluded_observer_wins_over_public_scope(self) -> None:
        """事实级排除优先于 public/community 等开放范围。"""
        loaded = self._load([_fact(excluded_observer_ids=["sakura"])])
        result = project_initial_knowledge(
            loaded,
            "sakura",
            KnowledgeRelationshipContext(community_observer_ids=frozenset(KNOWN_IDS)),
        )

        self.assertFalse(result.projections)
        self.assertEqual(result.excluded[0].rule, "excluded_observer")
        self.assertIn("excluded", result.excluded[0].reason)

    def test_invalid_ids_missing_template_and_confidence_fail_validation(self) -> None:
        """未知稳定 ID、适用模板缺失和非法 confidence 都必须阻止启动。"""
        cases = [
            (_fact(subject_ids=["unknown_npc"]), "unknown_id"),
            (
                _fact(knowledge_scope="participants", participant_ids=["sakura"]),
                "missing_projection_template",
            ),
            (_fact(confidence=1.2), "invalid_confidence"),
        ]
        for fact, reason in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                self._load([fact])

    def test_configuration_fact_ids_are_unique_and_stable(self) -> None:
        """正式配置中的事实 ID 应唯一且符合稳定 snake_case 约束。"""
        config_path = Path(__file__).parents[1] / "config" / "initial_knowledge.json"
        facts = load_initial_knowledge(config_path, known_ids=KNOWN_IDS)
        self.assertGreaterEqual(len(facts), 4)
        self.assertEqual(len({fact.fact_id for fact in facts}), len(facts))
        self.assertTrue(all(fact.fact_id == fact.fact_id.lower() for fact in facts))


if __name__ == "__main__":
    unittest.main()
