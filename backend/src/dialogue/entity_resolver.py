"""对话文本中的稳定实体解析。"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .conversation_context import ResolvedEntity
from .player_name import get_player_name_candidates


class DialogueEntityResolver:
    """优先使用配置中的稳定名称和别名解析 NPC、玩家与地点。"""

    def __init__(self, profiles_dir: str | Path, locations_path: str | Path | None = None):
        """从角色配置和共享地点配置建立确定性的别名索引。"""
        self.profiles_dir = Path(profiles_dir)
        self.locations_path = Path(locations_path) if locations_path else None
        self._aliases = self._build_alias_index()

    def resolve(self, utterance: str, recent_turns: list[str] | None = None) -> list[ResolvedEntity]:
        """从当前发言优先、近期对白辅助的文本中解析稳定实体。"""
        current = self._normalize(utterance)
        history = self._normalize(" ".join(recent_turns or []))
        matches: list[tuple[int, int, ResolvedEntity]] = []
        for alias, entity in self._aliases.items():
            normalized_alias = self._normalize(alias)
            if not normalized_alias:
                continue
            position = current.find(normalized_alias)
            source_rank = 0
            if position < 0:
                position = history.find(normalized_alias)
                source_rank = 1
            if position < 0:
                continue
            matches.append((source_rank, position, ResolvedEntity(
                entity_id=entity[0],
                entity_type=entity[1],
                display_name=entity[2],
                matched_alias=alias,
            )))

        resolved: list[ResolvedEntity] = []
        seen: set[tuple[str, str]] = set()
        for _, _, entity in sorted(matches, key=lambda item: (item[0], item[1], -len(item[2].matched_alias))):
            key = (entity.entity_type, entity.entity_id)
            if key not in seen:
                seen.add(key)
                resolved.append(entity)
        return resolved

    def _build_alias_index(self) -> dict[str, tuple[str, str, str]]:
        """汇总角色、玩家和地点的确定性别名。"""
        aliases: dict[str, tuple[str, str, str]] = {}
        for path in sorted(self.profiles_dir.glob("*.json")):
            try:
                profile = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            npc_id = path.stem
            display_name = str(profile.get("name") or npc_id)
            values = {npc_id, display_name}
            for key in ("aliases", "nicknames", "common_names"):
                raw = profile.get(key, [])
                if isinstance(raw, str):
                    values.add(raw)
                elif isinstance(raw, list):
                    values.update(str(item) for item in raw)
            if display_name.startswith("九条"):
                values.add("九条")
            for value in values:
                if value:
                    aliases[value] = (npc_id, "person", display_name)

        player_name = get_player_name_candidates()[0]
        for value in get_player_name_candidates() + ("玩家",):
            aliases[value] = ("player", "person", player_name)

        if self.locations_path and self.locations_path.exists():
            try:
                locations = json.loads(self.locations_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                locations = {}
            for zone_id, zone in locations.get("zones", {}).items():
                label = str(zone.get("label") or zone_id)
                aliases[zone_id] = (zone_id, "location", label)
                aliases[label] = (zone_id, "location", label)
        return aliases

    @staticmethod
    def _normalize(text: str) -> str:
        """移除不会影响中文实体匹配的空白和常见标点。"""
        return re.sub(r"[\s，。！？、,.!?：:；;（）()\[\]{}]", "", str(text)).casefold()

