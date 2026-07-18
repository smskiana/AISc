"""玩家单目标午夜印象与事件提取收口测试。"""
from __future__ import annotations

from backend.src.memory.manager import MemoryManager
from backend.src.npc.player_impression_refresh import (
    PlayerImpressionRefresher,
    build_nightly_player_direction,
    calculate_sociability_baseline,
)
from backend.src.memory.retrieval_contracts import RetrievalResult


class FakeStateManager:
    """提供输入冻结所需的最小状态 facade。"""

    db = object()

    def _load_profile(self, owner_id):
        """返回固定 NPC profile。"""
        return {"name": "樱", "personality": "温和"}

    def get_state(self, owner_id):
        """返回固定即时状态。"""
        return {"lingering_concern": "担心店里"}

    def _recent_target_memories(self, owner_id, target_id, game_day):
        """返回当日短期记忆。"""
        return "- 今天见过玩家"

    def get_impression_bundle(self, owner_id, target_id):
        """返回旧玩家印象。"""
        return {"text": "旧印象"}


class RecordingRetrieval:
    """记录固定方向检索请求。"""

    def __init__(self):
        self.requests = []

    def retrieve(self, request):
        """记录请求并返回结构化 trace。"""
        self.requests.append(request)
        return RetrievalResult(rebuilt_context="- 图记忆", diagnostics={"retrieval_trace_id": "trace_1"})


def test_fixed_nightly_direction_has_player_relationship_contract() -> None:
    """固定夜间方向覆盖玩家关系、近期事件与印象依据。"""
    direction = build_nightly_player_direction()
    assert direction.time_scope == "recent"
    assert direction.recall_intent == "compare_relationship"
    assert set(direction.themes) == {"relationship", "recent_activity", "past_event", "emotion"}
    assert set(direction.relation_facets) == {"affinity", "shared_event", "impression_basis"}


def test_prepare_inputs_uses_fixed_direction_without_llm_strategy_override() -> None:
    """输入冻结通过正式请求携带固定方向和稳定 trace 来源。"""
    retrieval = RecordingRetrieval()
    prepared = PlayerImpressionRefresher(FakeStateManager(), retrieval, ["sakura"]).prepare_inputs(4)

    request = retrieval.requests[0]
    assert request.mode == "nightly_impression"
    assert request.conversation_participant_ids == ["player"]
    assert request.direction_source == "nightly_fixed_player"
    assert request.direction_override.retrieval_query
    assert prepared[0].recent_memories == "- 今天见过玩家"
    assert prepared[0].retrieval_trace_id == "trace_1"


def test_refresher_excludes_player_from_configured_owner_ids() -> None:
    """配置集合即使包含 player，也只能计划真实 NPC owner。"""
    refresher = PlayerImpressionRefresher(FakeStateManager(), RecordingRetrieval(), ["sakura", "player"])
    assert refresher.npc_ids == ["sakura"]


def test_sociability_baseline_ignores_npc_impression_average() -> None:
    """次日社交基准只由 profile、当天 delta 与受限玩家 bias 决定。"""
    assert calculate_sociability_baseline(50.0, 10.0, 0.5) == 59.0
    assert calculate_sociability_baseline(50.0, 10.0, 99.0) == 65.0
    assert calculate_sociability_baseline(50.0, 10.0, -99.0) == 41.0


def test_extracted_edge_endpoint_validation_skips_missing_and_unknown_ids() -> None:
    """缺 from/to 和未知临时 ID 都不能进入写边阶段。"""
    id_map = {"n1": "node_sakura_event"}
    existing = {"node_sakura_player": "person"}
    assert MemoryManager._resolve_extracted_edge_ids({"to": "n1"}, id_map, existing) == (None, "node_sakura_event")
    assert MemoryManager._resolve_extracted_edge_ids({"from": "n1"}, id_map, existing) == ("node_sakura_event", None)
    assert MemoryManager._resolve_extracted_edge_ids({"from": "unknown", "to": "n1"}, id_map, existing) == (None, "node_sakura_event")
    assert MemoryManager._resolve_extracted_edge_ids({"from": "node_missing", "to": "n1"}, id_map, existing) == (None, "node_sakura_event")
    assert MemoryManager._resolve_extracted_edge_ids({"from": "node_sakura_player", "to": "n1"}, id_map, existing) == ("node_sakura_player", "node_sakura_event")
