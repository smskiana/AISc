"""NPC 任务 affordance 测试。"""
from __future__ import annotations

import unittest

from backend.src.npc.task_catalog import NpcTaskCatalog


class NpcTaskCatalogTests(unittest.TestCase):
    """验证任务和地点组合由共享 affordance 统一约束。"""

    def setUp(self) -> None:
        actions = {
            "actions": {
                "work": [{"id": "work_open"}, {"id": "work_tend"}],
                "routine": [{"id": "patrol"}],
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


if __name__ == "__main__":
    unittest.main()
