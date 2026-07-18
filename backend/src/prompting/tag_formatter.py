"""Profile、地点和关系信息的短标签渲染。"""

from typing import Any


def _tags(profile: dict[str, Any], key: str, fallback: str = "") -> str:
    """优先使用新标签字段，缺失时兼容旧字段。"""
    values = profile.get(key)
    if isinstance(values, list):
        return "、".join(str(item) for item in values if item) or fallback
    return str(values or fallback)


def format_npc(profile: dict[str, Any]) -> str:
    """把 NPC profile 压缩成稳定短标签块。"""
    return "；".join(filter(None, (
        f"性格：{_tags(profile, 'persona_tags', profile.get('personality', '未定义'))}",
        f"说话：{_tags(profile, 'speech_tags', profile.get('speech_style', '未定义'))}",
        f"社交：{_tags(profile, 'social_tags', '')}",
    )))


def format_location(profile: dict[str, Any] | None) -> str:
    """把地点 profile 压缩成氛围、感官和话题标签。"""
    profile = profile or {}
    return "；".join(filter(None, (
        f"氛围：{_tags(profile, 'mood_tags', profile.get('atmosphere', ''))}",
        f"感官：{_tags(profile, 'sensory_tags', '')}",
        f"话题：{_tags(profile, 'topic_tags', '')}",
    ))) or "（无地点标签）"
