"""玩家快捷回复安全摘要的容量、筛选和隐私边界测试。"""
from backend.src.dialogue.reply_suggestion_diagnostics import ReplySuggestionTraceStore


def test_reply_suggestion_trace_is_bounded_filterable_and_preview_only() -> None:
    """trace 应裁剪正文、保留拒绝原因，并按最近记录筛选。"""
    store = ReplySuggestionTraceStore(capacity=2, preview_limit=6)
    first_id = store.record(
        npc_id="sakura",
        player_id="player",
        context_keys=["npc_name", "player_name"],
        choices=["这是玩家可以直接发送的一句很长台词"],
        rejected_choices=[{"choice": "鹿岛樱：这是不应保留的完整台词", "reason": "npc_name_prefix"}],
        fallback_used=True,
        failure_reason="",
        elapsed_ms=12,
    )
    store.record(
        npc_id="kujo",
        player_id="player",
        context_keys=["npc_name"],
        choices=["我知道了。"],
        rejected_choices=[],
        fallback_used=False,
        failure_reason="",
        elapsed_ms=3,
    )
    latest_id = store.record(
        npc_id="sakura",
        player_id="player",
        context_keys=["npc_name"],
        choices=["那后来怎么样了？"],
        rejected_choices=[],
        fallback_used=False,
        failure_reason="",
        elapsed_ms=4,
    )

    snapshots = store.snapshot(npc_id="sakura", limit=10)

    assert first_id != latest_id
    assert [item["reply_trace_id"] for item in snapshots] == [latest_id]
    assert store.snapshot(reply_trace_id=first_id) == []
    assert snapshots[0]["speaker_role_expected"] == "player"
    assert snapshots[0]["recipient_role_expected"] == "npc"


def test_reply_suggestion_trace_crops_rejected_text_and_keeps_reason() -> None:
    """诊断允许有限预览，但不能保存完整被拒文本。"""
    store = ReplySuggestionTraceStore(preview_limit=6)
    trace_id = store.record(
        npc_id="sakura",
        player_id="player",
        context_keys=["npc_name"],
        choices=["我会认真考虑这件事的。"],
        rejected_choices=[{"choice": "（微微歪头）这是很长的舞台动作说明", "reason": "leading_stage_direction"}],
        fallback_used=True,
        failure_reason="generation_failed:RuntimeError",
        elapsed_ms=7,
    )

    snapshot = store.snapshot(reply_trace_id=trace_id)[0]

    assert snapshot["choice_previews"] == ["我会认真考虑..."]
    assert snapshot["rejected_choice_previews"] == ["（微微歪头）..."]
    assert snapshot["rejection_reasons"] == ["leading_stage_direction"]
    assert "这是很长的舞台动作说明" not in snapshot["rejected_choice_previews"][0]
