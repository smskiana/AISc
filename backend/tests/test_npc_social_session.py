"""NPC-NPC 社交纯内容与完成提交协议测试。"""
from __future__ import annotations

import unittest

from backend.src.npc.social_session import NpcSocialContentService


class FakeDialogueManager:
    """记录内容生成与有效 COMPLETE 后的记忆提交。"""

    def __init__(self):
        self.generated: list[str] = []
        self.committed: list[tuple] = []

    async def generate_prepared_social(self, request_id, npc_a, npc_b, location, game_time):
        """返回两句稳定测试内容。"""
        self.generated.append(request_id)
        return [(npc_a, "你好"), (npc_b, "你好")]

    def commit_prepared_social(self, npc_a, npc_b, lines, location, game_time, base_world_revision=0, operation_id=""):
        """记录 Unity COMPLETE 后的提交。"""
        self.committed.append((npc_a, npc_b, lines, location, game_time, base_world_revision, operation_id))
        return {"summary": "千早和九条聊了几句。", "effects": []}


class NpcSocialContentTests(unittest.IsolatedAsyncioTestCase):
    """验证 Python 只生成内容，且只接受 Unity 有效 COMPLETE。"""

    async def asyncSetUp(self) -> None:
        """创建可观察内容服务与重规划回调。"""
        self.replanned: list[dict] = []
        self.dialogue = FakeDialogueManager()

        async def replan(context: dict) -> None:
            self.replanned.append(context)

        self.service = NpcSocialContentService(self.dialogue, completion_callback=replan)
        self.request = {
            "request_id": "social_1",
            "candidate_id": "candidate_1",
            "npc_id": "chihaya",
            "target_npc_id": "kujo",
            "actual_location_id": "street.crossroad",
            "world_revision": 7,
            "game_time": {"day": 1, "hour": 10, "minute": 0, "weather": "sunny", "time_revision": 3},
        }

    async def test_content_request_is_idempotent_and_does_not_commit(self) -> None:
        """重复内容请求只生成一次，COMPLETE 前绝不写记忆。"""
        first = await self.service.handle_content_request(self.request)
        second = await self.service.handle_content_request(self.request)
        self.assertEqual(first, second)
        self.assertEqual(self.dialogue.generated, ["social_1"])
        self.assertEqual(self.dialogue.committed, [])
        self.assertEqual(first["type"], "NPC_SOCIAL_CONTENT_RESULT")
        self.assertEqual(len(first["lines"]), 2)

    async def test_valid_complete_commits_and_replans(self) -> None:
        """匹配参与者和非陈旧 revision 的 COMPLETE 才提交。"""
        await self.service.handle_content_request(self.request)
        result = await self.service.handle_complete({
            **self.request,
            "world_revision": 8,
        })
        self.assertTrue(result["accepted"])
        self.assertEqual(len(self.dialogue.committed), 1)
        self.assertEqual(self.dialogue.committed[0][5], 8)
        self.assertEqual(self.replanned[0]["npc_ids"], ["chihaya", "kujo"])

    async def test_stale_or_mismatched_complete_never_commits(self) -> None:
        """迟到 revision 和参与者串线都不得写入记忆。"""
        await self.service.handle_content_request(self.request)
        stale = await self.service.handle_complete({**self.request, "world_revision": 6})
        self.assertEqual(stale["reason"], "stale_world_revision")
        mismatch = await self.service.handle_complete({
            **self.request,
            "target_npc_id": "sakura",
            "world_revision": 8,
        })
        self.assertEqual(mismatch["reason"], "participant_mismatch")
        self.assertEqual(self.dialogue.committed, [])

    async def test_failed_session_discards_content_without_memory(self) -> None:
        """Unity 失败终态只清理缓存，不提交记忆。"""
        await self.service.handle_content_request(self.request)
        result = self.service.discard(self.request)
        self.assertTrue(result["accepted"])
        complete = await self.service.handle_complete(self.request)
        self.assertFalse(complete["accepted"])
        self.assertEqual(self.dialogue.committed, [])


if __name__ == "__main__":
    unittest.main()
