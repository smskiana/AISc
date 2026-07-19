"""NPC 任务 affordance 测试。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from backend.src.npc.task_catalog import NpcTaskCatalog


class NpcTaskCatalogTests(unittest.TestCase):
    """验证任务和地点组合由共享 affordance 统一约束。"""

    def setUp(self) -> None:
        actions = {
            "actions": {
                "work": [{"id": "work_open"}, {"id": "work_tend"}],
                "routine": [{"id": "patrol"}],
            },
            "task_runtime_metadata": {
                "work_open": {"segment_id": "work", "completion_policy_id": "state_condition", "interrupt_policy": "non_interruptible", "duration_gameplay_seconds": 5, "lifecycle_action": True},
                "work_tend": {"segment_id": "work", "completion_policy_id": "duration", "interrupt_policy": "player_interruptible", "duration_gameplay_seconds": 300},
                "patrol": {"segment_id": "work", "completion_policy_id": "duration", "interrupt_policy": "player_interruptible", "duration_gameplay_seconds": 60},
            },
            "action_affordances": {
                "work_open": {
                    "location_tags": ["shop_doorway"],
                    "allowed_npcs": ["sakura"],
                },
                "work_tend": {
                    "location_tags": ["shop_service"],
                },
                "patrol": {
                    "location_tags": ["patrol_spot"],
                    "allowed_npcs": ["kujo"],
                },
            },
        }
        locations = {
            "zones": {
                "flower_shop": {"spots": ["doorway", "workbench"]},
                "bakery": {"spots": ["counter"]},
                "wagashi": {"spots": ["counter"]},
                "street": {"spots": ["crossroad"]},
            },
            "spot_tags": {
                "flower_shop.doorway": ["shop_doorway"],
                "flower_shop.workbench": ["work_surface"],
                "bakery.counter": ["shop_service"],
                "wagashi.counter": ["shop_service"],
                "street.crossroad": ["patrol_spot"],
            },
        }
        self.catalog = NpcTaskCatalog(actions, locations)

    def test_valid_action_location_role_combination(self) -> None:
        """匹配的任务、spot 和 NPC 身份应通过。"""
        self.assertEqual(
            self.catalog.validate_task("sakura", "work_open", "flower_shop.doorway"),
            (True, ""),
        )

    def test_wrong_spot_or_role_is_rejected(self) -> None:
        """合法 ID 的错误组合也必须被拒绝。"""
        self.assertEqual(
            self.catalog.validate_task("sakura", "work_open", "flower_shop.workbench")[1],
            "location_not_afforded",
        )
        self.assertEqual(
            self.catalog.validate_task("kujo", "work_open", "flower_shop.doorway")[1],
            "npc_not_allowed",
        )

    def test_work_actions_are_limited_to_owner_zone(self) -> None:
        """工作类任务不能只凭 shop tag 跨店执行。"""
        self.assertEqual(
            self.catalog.validate_task("tatsunosuke", "work_tend", "wagashi.counter"),
            (True, ""),
        )
        self.assertEqual(
            self.catalog.validate_task("tatsunosuke", "work_tend", "bakery.counter")[1],
            "npc_not_allowed",
        )

    def test_runtime_metadata_is_explicit_and_lifecycle_actions_are_marked(self) -> None:
        """目录应统一投影运行时策略，生命周期动作不得混入普通队列。"""
        metadata = self.catalog.task_runtime_metadata("work_open")
        self.assertEqual(metadata["segment_id"], "work")
        self.assertEqual(metadata["completion_policy_id"], "state_condition")
        self.assertTrue(metadata["lifecycle_action"])
        self.assertEqual(self.catalog.validate_runtime_metadata("work_open"), (True, ""))

    def test_duration_policy_requires_positive_gameplay_duration(self) -> None:
        """duration 策略不得回退到无语义的零秒或固定一秒。"""
        self.catalog._runtime_metadata["work_tend"]["duration_gameplay_seconds"] = 0
        self.assertEqual(
            self.catalog.validate_runtime_metadata("work_tend"),
            (False, "invalid_duration_gameplay_seconds"),
        )

    def test_shared_catalog_declares_runtime_metadata_for_every_formal_action(self) -> None:
        """真实共享目录中的所有正式 action 都必须具备完整运行时策略。"""
        shared_dir = Path(__file__).resolve().parents[2] / "shared"
        actions = json.loads((shared_dir / "actions.json").read_text(encoding="utf-8"))
        locations = json.loads((shared_dir / "locations.json").read_text(encoding="utf-8"))
        catalog = NpcTaskCatalog(actions, locations)

        failures = {
            action_id: catalog.validate_runtime_metadata(action_id)[1]
            for action_id in sorted(catalog.action_ids)
            if not catalog.validate_runtime_metadata(action_id)[0]
        }
        self.assertEqual(failures, {})
        self.assertTrue(catalog.task_runtime_metadata("work_open")["lifecycle_action"])
        self.assertTrue(catalog.task_runtime_metadata("work_close")["lifecycle_action"])


if __name__ == "__main__":
    unittest.main()
