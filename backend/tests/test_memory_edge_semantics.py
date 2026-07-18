"""记忆图边语义规则回归测试。"""

import unittest

from backend.src.memory.edge_semantics import initial_relationship_clarity


class InitialRelationshipClarityTests(unittest.TestCase):
    """验证冷启动人物关系 clarity 不再由 bond 直接决定。"""

    def test_core_person_low_bond_keeps_recognition_floor(self) -> None:
        """低 bond 的核心人物关系仍保留稳定基础认知。"""
        clarity_ab, clarity_ba = initial_relationship_clarity(
            recognition_importance=0.9,
            bond=0.15,
            is_core_person=True,
        )

        self.assertGreaterEqual(clarity_ab, 0.72)
        self.assertLessEqual(clarity_ab, 0.8)
        self.assertGreaterEqual(clarity_ba, 0.6)
        self.assertLessEqual(clarity_ba, 0.7)

    def test_core_person_high_bond_only_slightly_raises_clarity(self) -> None:
        """高 bond 只能小幅抬高 clarity，不能突破合法上限。"""
        low_ab, low_ba = initial_relationship_clarity(
            recognition_importance=0.9,
            bond=0.15,
            is_core_person=True,
        )
        high_ab, high_ba = initial_relationship_clarity(
            recognition_importance=0.9,
            bond=0.9,
            is_core_person=True,
        )

        self.assertGreater(high_ab, low_ab)
        self.assertLessEqual(high_ab, 0.88)
        self.assertGreater(high_ba, low_ba)
        self.assertLessEqual(high_ba, 0.78)
        self.assertLessEqual(high_ab, 1.0)
        self.assertLessEqual(high_ba, 1.0)

    def test_initial_relationship_rule_is_not_person_specific(self) -> None:
        """玩家、主要 NPC 和未来核心人物共用同一冷启动关系规则。"""
        player_rule = initial_relationship_clarity(
            recognition_importance=0.9,
            bond=0.2,
            is_core_person=True,
        )
        npc_rule = initial_relationship_clarity(
            recognition_importance=0.9,
            bond=0.2,
            is_core_person=True,
        )
        future_core_rule = initial_relationship_clarity(
            recognition_importance=0.9,
            bond=0.2,
            is_core_person=True,
        )

        self.assertEqual(player_rule, npc_rule)
        self.assertEqual(npc_rule, future_core_rule)


if __name__ == "__main__":
    unittest.main()
