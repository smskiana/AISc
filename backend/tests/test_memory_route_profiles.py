"""记忆路由三档二分搜索的纯函数测试。"""
import unittest

from backend.scripts.tune_memory_route_profiles import (
    binary_search_profile,
    evaluate_thresholds,
    selection_overlap,
    thresholds_for_aggressiveness,
)


class MemoryRouteProfileTests(unittest.TestCase):
    """验证路由激进度、效果计算与二分边界。"""

    def test_aggressiveness_lowers_both_thresholds(self):
        """激进度提高时最低分和领先差必须同时单调降低。"""
        strict = thresholds_for_aggressiveness(0.0)
        middle = thresholds_for_aggressiveness(0.5)
        permissive = thresholds_for_aggressiveness(1.0)

        self.assertGreater(strict["min_score"], middle["min_score"])
        self.assertGreater(middle["min_score"], permissive["min_score"])
        self.assertGreater(strict["margin"], middle["margin"])
        self.assertGreater(middle["margin"], permissive["margin"])

    def test_selection_overlap_uses_baseline_recall(self):
        """选边重合度以稳定 LLM 基线的召回比例计算。"""
        self.assertEqual(selection_overlap(["a", "b"], ["a", "c"]), 0.5)
        self.assertEqual(selection_overlap([], []), 1.0)

    def test_evaluation_counts_llm_savings_and_quality(self):
        """本地接管应同时反映到 LLM 节省率和整体效果保持率。"""
        samples = [
            {
                "max_select": 1,
                "scores": [2.0, 0.5],
                "local_selection": ["a"],
                "baseline_selection": ["a"],
            },
            {
                "max_select": 1,
                "scores": [1.2, 1.1],
                "local_selection": ["b"],
                "baseline_selection": ["c"],
            },
        ]

        metrics = evaluate_thresholds(samples, {"min_score": 1.5, "margin": 0.5})

        self.assertEqual(metrics["local_takeovers"], 1)
        self.assertEqual(metrics["llm_savings_rate"], 0.5)
        self.assertEqual(metrics["quality_retention"], 1.0)

    def test_binary_search_finds_most_aggressive_valid_point(self):
        """二分搜索应靠近效果约束允许的最激进边界。"""
        samples = [
            {
                "max_select": 1,
                "scores": [2.2, 0.4],
                "local_selection": ["a"],
                "baseline_selection": ["a"],
            },
            {
                "max_select": 1,
                "scores": [1.0, 0.95],
                "local_selection": ["b"],
                "baseline_selection": ["c"],
            },
        ]

        profile = binary_search_profile(samples, quality_floor=0.75, iterations=24)

        self.assertGreaterEqual(profile["quality_retention"], 0.75)
        self.assertEqual(profile["local_takeovers"], 1)


if __name__ == "__main__":
    unittest.main()
