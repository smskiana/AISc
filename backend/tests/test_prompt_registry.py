"""Prompt 数据层注册表完整性测试。"""

import json
from pathlib import Path

from backend.src.prompting import PromptAssembler


def test_all_prompt_tasks_reference_existing_contracts() -> None:
    """十个首期任务均可加载并生成 messages。"""
    assembler = PromptAssembler()
    expected = {
        "player_dialogue", "npc_dialogue", "player_reply_suggestions",
        "npc_daily_plan", "npc_replan_after_social", "npc_social_intent",
        "nightly_impression", "memory_extract", "memory_merge", "memory_route", "memory_direction",
    }
    assert set(assembler.registry._tasks) == expected
    for task_id in expected:
        messages = assembler.build(task_id, {})
        assert messages and messages[0]["content"]


def test_profile_tags_fallback_to_legacy_fields() -> None:
    """旧 profile 没有新标签时仍能稳定渲染。"""
    assembler = PromptAssembler()
    message = assembler.build("player_dialogue", {
        "profile": {"name": "测试", "personality": "谨慎", "speech_style": "简短"},
    })[0]["content"]
    assert "性格：谨慎" in message
    assert "说话：简短" in message


def test_profiles_contain_first_wave_tags() -> None:
    """首期 NPC profile 均提供轻量标签。"""
    root = Path(__file__).parents[1] / "config" / "npc_profiles"
    for path in root.glob("*.json"):
        profile = json.loads(path.read_text(encoding="utf-8"))
        assert profile["persona_tags"]
        assert profile["speech_tags"]
        assert profile["social_tags"]


def test_location_profiles_contain_first_wave_tags() -> None:
    """主要地点 profile 均提供氛围、感官和话题标签。"""
    root = Path(__file__).parents[1] / "config" / "location_profiles"
    for path in root.glob("*.json"):
        profile = json.loads(path.read_text(encoding="utf-8"))
        assert profile["mood_tags"]
        assert profile["sensory_tags"]
        assert profile["topic_tags"]
