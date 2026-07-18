"""玩家昵称与 prompt 占位符渲染工具。"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_PLAYER_NAME = "玩家"
DEFAULT_PLAYER_NICKNAME = "小李"
PLAYER_NICKNAME_TOKENS = ("{player_nickname}", "{{player_nickname}}")
PLAYER_NAME_TOKENS = ("{player_name}", "{{player_name}}")
PLAYER_LABEL_TOKENS = ("{player_label}", "{{player_label}}")


def player_profile_path() -> Path:
    """返回玩家 profile 配置路径。"""
    return Path(__file__).resolve().parents[2] / "config" / "player_profile.json"


def load_player_profile() -> dict:
    """读取玩家 profile，缺失时返回默认昵称配置。"""
    path = player_profile_path()
    if not path.exists():
        return {"id": "player", "name": DEFAULT_PLAYER_NAME, "nickname": DEFAULT_PLAYER_NICKNAME}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"id": "player", "name": DEFAULT_PLAYER_NAME, "nickname": DEFAULT_PLAYER_NICKNAME}


def get_player_name() -> str:
    """读取玩家语义名，默认是“玩家”。"""
    name = str(load_player_profile().get("name", "")).strip()
    return name or DEFAULT_PLAYER_NAME


def get_player_nickname() -> str:
    """读取玩家昵称，默认是“小李”。"""
    nickname = str(load_player_profile().get("nickname", "")).strip()
    return nickname or DEFAULT_PLAYER_NICKNAME


def get_player_display_name() -> str:
    """返回对话中可自然称呼玩家的显示名。"""
    return get_player_nickname()


def get_player_profile_label() -> str:
    """返回带昵称语义的玩家标签，供感知层和 prompt 使用。"""
    name = get_player_name()
    nickname = get_player_nickname()
    if nickname and nickname != name:
        return f"{name}（昵称：{nickname}）"
    return name


def get_player_name_candidates() -> tuple[str, ...]:
    """返回检索和事实守卫可识别的玩家称呼集合。"""
    values = [get_player_nickname(), get_player_name(), DEFAULT_PLAYER_NICKNAME, DEFAULT_PLAYER_NAME]
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return tuple(result)


def render_player_tokens(text: str, replace_legacy_default: bool = True) -> str:
    """在送入 prompt 前渲染玩家昵称占位符和旧默认昵称。"""
    rendered = str(text or "")
    name = get_player_name()
    nickname = get_player_nickname()
    label = get_player_profile_label()
    replacements = {
        PLAYER_NICKNAME_TOKENS: nickname,
        PLAYER_NAME_TOKENS: name,
        PLAYER_LABEL_TOKENS: label,
    }
    for tokens, value in replacements.items():
        for token in tokens:
            rendered = rendered.replace(token, value)
    if replace_legacy_default and nickname != DEFAULT_PLAYER_NICKNAME:
        rendered = rendered.replace(DEFAULT_PLAYER_NICKNAME, nickname)
    return rendered


def render_player_tokens_in_messages(messages: list[dict]) -> list[dict]:
    """渲染 messages 中的系统生成文本，返回新的 message 列表。"""
    rendered_messages: list[dict] = []
    for message in messages:
        copied = dict(message)
        copied["content"] = render_player_tokens(str(copied.get("content", "")))
        rendered_messages.append(copied)
    return rendered_messages
