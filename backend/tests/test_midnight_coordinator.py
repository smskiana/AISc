"""午夜协调器的并发顺序、局部失败和诊断测试。"""
from __future__ import annotations

import asyncio
import time

from backend.src.memory.midnight_coordinator import MidnightCoordinator, MidnightSnapshotStore
from backend.src.npc.player_impression_refresh import (
    PlayerImpressionBatchResult,
    PlayerImpressionInput,
    PlayerImpressionOutput,
)


class FakeImpressionRefresher:
    """记录协调器调用顺序并模拟耗时玩家印象生成。"""

    npc_ids = ["sakura"]

    def __init__(self, events: list[str], fallback: bool = False):
        self.events = events
        self.fallback = fallback

    def prepare_inputs(self, game_day: int):
        """返回一份已冻结输入。"""
        self.events.append("prepare")
        return [PlayerImpressionInput(0, "sakura", "樱", "温和", "", "recent", "graph", "previous", "trace_1")]

    def generate(self, inputs):
        """模拟耗时生成分支。"""
        self.events.append("impression_start")
        time.sleep(0.06)
        self.events.append("impression_end")
        output = PlayerImpressionOutput(inputs[0], {"baseline_impression": "ok", "speech_hint": "ok", "approach_bias": 0.1}, self.fallback)
        return PlayerImpressionBatchResult(
            outputs=[output], planned_count=1,
            success_count=0 if self.fallback else 1,
            fallback_count=1 if self.fallback else 0,
            failed_owner_ids=["sakura"] if self.fallback else [],
            elapsed_sec=0.06,
        )

    def commit(self, batch, game_day):
        """记录提交发生在图演化之后。"""
        self.events.append("commit")

    def refresh_next_day_baselines(self, game_day):
        """记录状态刷新阶段。"""
        self.events.append("refresh")


def test_heavy_branches_overlap_and_evolution_waits_for_extraction() -> None:
    """两个重阶段应重叠，且图演化必须等待事件提取结束。"""
    events: list[str] = []
    refresher = FakeImpressionRefresher(events)

    async def extract():
        """模拟耗时事件提取分支。"""
        events.append("extract_start")
        await asyncio.sleep(0.06)
        events.append("extract_end")
        return {"event_owner_count": 1, "success_count": 1, "failure_count": 0}

    async def evolve():
        """记录演化开始。"""
        events.append("evolve")

    coordinator = MidnightCoordinator(
        refresher,
        lambda: events.append("decay"),
        extract,
        evolve,
        lambda: events.append("cleanup"),
        MidnightSnapshotStore(),
    )
    result = asyncio.run(coordinator.run(4))

    assert result.status == "success"
    assert result.parallel_wall_sec < 0.11
    assert events.index("extract_start") < events.index("impression_end")
    assert events.index("extract_end") < events.index("evolve") < events.index("commit")
    assert result.retrieval_trace_ids == {"sakura": "trace_1"}


def test_branch_fallback_and_extraction_failure_report_partial_failure() -> None:
    """印象 fallback 或提取局部失败必须形成 partial_failure 终态。"""
    events: list[str] = []
    refresher = FakeImpressionRefresher(events, fallback=True)

    async def extract():
        """返回可诊断的单 NPC 提取失败。"""
        return {
            "event_owner_count": 1,
            "success_count": 0,
            "failure_count": 1,
            "failed_owner_ids": ["sakura"],
            "invalid_edge_count": 2,
        }

    async def evolve():
        """允许局部失败后继续执行图演化。"""
        return None

    store = MidnightSnapshotStore()
    result = asyncio.run(MidnightCoordinator(
        refresher, lambda: None, extract, evolve, lambda: None, store,
    ).run(4))

    assert result.status == "partial_failure"
    assert result.impression_fallback_count == 1
    assert result.extraction_failure_count == 1
    assert result.extraction_invalid_edge_count == 2
    assert store.snapshot()["status"] == "partial_failure"
