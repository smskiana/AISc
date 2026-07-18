"""Unity 候选驱动的 NPC 社交语义决策测试。"""
from __future__ import annotations

import unittest

from backend.src.npc.social_decision import NpcSocialDecisionService


class SocialDecisionTests(unittest.IsolatedAsyncioTestCase):
    """验证 decision 幂等、版本关联和失败默认值。"""

    def _payload(self) -> dict:
        """返回合法的冻结物理候选输入。"""
        return {
            "request_id": "request_1",
            "candidate_id": "candidate_1",
            "npc_id": "sakura",
            "target_npc_id": "chihaya",
            "location_id": "street.crossroad",
            "world_revision": 17,
            "game_time": {"day": 2, "hour": 17, "minute": 5, "weather": "sunny", "time_revision": 9},
        }

    async def test_same_request_is_idempotent_and_returns_revision(self):
        """重复 request 只调用一次语义 owner，并原样返回 world revision。"""
        calls = 0

        async def decide(_request):
            nonlocal calls
            calls += 1
            return True, "friend_nearby", "greeting"

        service = NpcSocialDecisionService(decide)
        first = await service.decide(self._payload())
        second = await service.decide(self._payload())
        self.assertEqual(1, calls)
        self.assertEqual(first, second)
        self.assertEqual(17, first["world_revision"])

    async def test_provider_failure_declines_without_freezing_unity(self):
        """供应商失败必须默认拒绝，不能要求 Unity 锁定双方。"""
        async def fail(_request):
            raise RuntimeError("provider_down")

        result = await NpcSocialDecisionService(fail).decide(self._payload())
        self.assertFalse(result["want_to_talk"])
        self.assertEqual("social_decision_unavailable", result["reason"])

    async def test_invalid_time_is_rejected_before_semantic_call(self):
        """非法冻结时间不得进入关系或 LLM 语义层。"""
        payload = self._payload()
        payload["game_time"]["hour"] = 24
        with self.assertRaisesRegex(ValueError, "invalid_game_time_snapshot"):
            await NpcSocialDecisionService(lambda _: None).decide(payload)


if __name__ == "__main__":
    unittest.main()
