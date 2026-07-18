"""日程三层候选的物理过滤和记忆证据测试。"""
from __future__ import annotations

import unittest

from backend.src.memory.retrieval_contracts import RetrievalResult
from backend.src.npc.schedule_candidates import ScheduleCandidateBuilder, apply_memory_scores
from backend.src.npc.schedule_memory_evidence import ScheduleMemoryEvidenceProvider


class _Catalog:
    """提供物理过滤测试所需的最小 affordance 集。"""

    action_ids = {"eat", "read", "visit", "work_open"}

    def allowed_locations(self, npc_id, action_id):
        """为每个动作提供稳定测试地点。"""
        return [f"zone.{action_id}"]


class ScheduleCandidateTests(unittest.TestCase):
    """验证第一层硬过滤和第二层证据增强不越权。"""

    def test_closed_and_unreachable_candidates_are_removed(self):
        """关闭和不可达地点不得进入 LLM 候选。"""
        candidates, rejections = ScheduleCandidateBuilder(_Catalog()).build("sakura", [], {"locations": {"zone.read": {"open_state": "closed"}, "zone.visit": {"reachable_state": "unreachable"}}})
        locations = {item.location_id for item in candidates}
        self.assertNotIn("zone.read", locations)
        self.assertNotIn("zone.visit", locations)
        self.assertEqual(1, rejections["business_closed"])
        self.assertEqual(1, rejections["travel_time_exceeded"])

    def test_no_memory_keeps_required_candidates(self):
        """没有长期记忆时职业和基础 need 候选仍被保留。"""
        candidates, _ = ScheduleCandidateBuilder(_Catalog()).build("sakura", [], {})
        enhanced = apply_memory_scores(candidates, {})
        self.assertTrue(any(item.primary_group == "need" for item in enhanced))
        self.assertTrue(any(item.primary_group == "occupation" for item in enhanced))

    def test_evidence_provider_keeps_ids_scores_and_trace_only(self):
        """检索层只向候选暴露证据 ID、评分和 trace ID。"""
        def retrieve(_request):
            return RetrievalResult(retrieved_node_ids=["memory.1"], diagnostics={"retrieval_trace_id": "trace.1", "path_evidence": [{"node_id": "memory.2", "score": 0.7}], "vector_hit_usage": [{"similarity": 0.8}]})

        candidates, _ = ScheduleCandidateBuilder(_Catalog()).build("sakura", [], {})
        evidence, stats = ScheduleMemoryEvidenceProvider(retrieve).enrich("sakura", candidates, "08:00")
        self.assertEqual(0.8, evidence["need"]["similarity"])
        self.assertIn("memory.1", evidence["need"]["evidence_ids"])
        self.assertGreater(stats["memory_queries"], 0)


if __name__ == "__main__":
    unittest.main()
