"""玩家快捷回复主体契约和确定性收口回归测试。"""
from pathlib import Path

from backend.src.application.dialogue_service import PlayerDialogueService
from backend.src.dialogue.prompt_builder import PromptBuilder


class FakeDatabase:
    """提供快捷回复 Prompt 所需的空状态和空记忆读取。"""

    def fetchone(self, query, params=()):
        """本测试不提供持久化状态，让 Builder 走稳定回退。"""
        return None

    def fetchall(self, query, params=()):
        """本测试不提供短期记忆。"""
        return []


def test_player_reply_prompt_keeps_player_speaker_and_npc_recipient() -> None:
    """公开 PromptBuilder seam 必须渲染双方身份及 NPC 背景方向。"""
    root = Path(__file__).parents[1]
    builder = PromptBuilder(FakeDatabase(), str(root / "config" / "npc_profiles"))

    message = builder.build_player_reply_suggestions(
        "sakura",
        target_id="player",
        npc_reply="今天的花开得很好。",
        dialogue_messages=[{"role": "assistant", "content": "要看看新到的花吗？"}],
        game_time="第1天 10:00",
        location="flower_shop.doorway",
    )[0]["content"]

    assert "玩家（唯一发言者）：小李" in message
    assert "当前 NPC（唯一接收者）：鹿岛樱" in message
    assert "当前 NPC：小李" not in message
    assert "NPC 的说话语气（仅作理解背景，不定义玩家口吻）" in message
    assert "不得替 NPC 回答" in message


def test_parser_rejects_npc_prefix_and_leading_stage_direction_then_falls_back() -> None:
    """确定性主体违规应被拒绝，并由既有 fallback 补足三条选择。"""
    service = PlayerDialogueService(None, FakeDatabase(), None, None)
    raw = '{"choices":["鹿岛樱：我也这么觉得。","（微微歪头）那你想怎么做？","那后来怎么样了？"]}'

    parsed, rejected = service._parse_player_reply_choices(raw, "鹿岛樱", include_rejections=True)
    merged = service._merge_with_fallback_choices(parsed, "今天的花开得很好。")

    assert parsed == ["那后来怎么样了？"]
    assert [item["reason"] for item in rejected] == ["npc_name_prefix", "leading_stage_direction"]
    assert len(merged) == 3
    assert all(not item.startswith("鹿岛樱：") for item in merged)
    assert all(not item.startswith("（") for item in merged)
