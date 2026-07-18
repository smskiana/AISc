"""对话现场感知上下文构建器。"""
from __future__ import annotations

import json
from pathlib import Path

from .player_name import get_player_profile_label, render_player_tokens
from ..world.location_state import is_transit_location


class PerceptionContextBuilder:
    """从地点、物品、人物配置中提取当前对话可感知信息。"""

    def __init__(self, profiles_dir: str | Path):
        self.profiles_dir = Path(profiles_dir)
        self.config_dir = self.profiles_dir.parent
        self.location_profiles_dir = self.config_dir / "location_profiles"
        self.player_profile_path = self.config_dir / "player_profile.json"
        self.items_path = self.config_dir.parent.parent / "shared" / "items.json"
        self._npc_cache: dict[str, dict] = {}
        self._location_cache: dict[str, dict] = {}
        self._items_cache: list[dict] | None = None
        self._player_cache: dict | None = None

    def build_player_dialogue(self, npc_id: str, target_id: str,
                              location_id: str, game_time: str) -> str:
        """构建玩家与 NPC 对话使用的现场感知。"""
        return self._build_context(location_id, game_time, [npc_id, target_id])

    def build_npc_dialogue(self, npc_a: str, npc_b: str,
                           location_id: str, game_time: str) -> str:
        """构建 NPC 之间闲聊使用的现场感知。"""
        return self._build_context(location_id, game_time, [npc_a, npc_b])

    def _build_context(self, location_id: str, game_time: str,
                       participant_ids: list[str]) -> str:
        """按当前地点和参与者输出紧凑的感知段落。"""
        if is_transit_location(location_id):
            lines = [
                "# 现场感知",
                "位置：正在移动途中，不属于任何地区；不要引用出发地或目标地的固定物件、气味和局部景象。",
            ]
            people = self._format_people_lines(participant_ids)
            if people:
                lines.append("人物感知：")
                lines.extend(people)
            lines.append("使用规则：只能描述人物当前可见表现，不要把任何地区当成已经到达的现场。")
            return "\n".join(lines)

        zone_id, spot_id = self._split_location(location_id)
        location = self._load_location(zone_id)
        if not location and not participant_ids:
            return ""

        lines = ["# 现场感知"]
        location_line = self._format_location_line(location, zone_id, spot_id, game_time)
        if location_line:
            lines.append(location_line)

        spot_line = self._format_spot_line(location, spot_id)
        if spot_line:
            lines.append(spot_line)

        sensory_line = self._format_sensory_line(location)
        if sensory_line:
            lines.append(sensory_line)

        objects_line = self._format_objects_line(location, zone_id, spot_id)
        if objects_line:
            lines.append(objects_line)

        people = self._format_people_lines(participant_ids)
        if people:
            lines.append("人物感知：")
            lines.extend(people)

        lines.append("使用规则：只能把这里列出的内容当作当前能看见、听见或闻到的东西；没有列出的物品和关系不要当成亲眼所见。")
        return "\n".join(lines)

    def _format_location_line(self, location: dict, zone_id: str,
                              spot_id: str, game_time: str) -> str:
        """格式化地点总览与当前时段氛围。"""
        if not location:
            return f"地点：{zone_id}.{spot_id}" if spot_id else f"地点：{zone_id}"

        name = location.get("name", zone_id)
        tags = self._join(location.get("perception_tags"))
        atmosphere = str(location.get("atmosphere", "")).strip()
        time_key = self._time_key(game_time)
        time_text = str((location.get("time_atmosphere") or {}).get(time_key, "")).strip()

        parts = [f"地点：{name}"]
        if tags:
            parts.append(f"标签：{tags}")
        if atmosphere:
            parts.append(f"氛围：{atmosphere}")
        if time_text:
            parts.append(f"此时：{time_text}")
        return "；".join(parts)

    def _format_spot_line(self, location: dict, spot_id: str) -> str:
        """格式化当前 spot 的局部感知。"""
        if not location or not spot_id:
            return ""

        spot_text = str((location.get("spots") or {}).get(spot_id, "")).strip()
        spot_data = (location.get("spot_perception") or {}).get(spot_id, {})
        spot_tags = self._join(spot_data.get("tags"))
        spot_objects = self._join(spot_data.get("visible_objects"))
        hooks = self._join(spot_data.get("conversation_hooks"))

        parts = []
        if spot_text:
            parts.append(f"当前位置：{spot_text}")
        if spot_tags:
            parts.append(f"局部标签：{spot_tags}")
        if spot_objects:
            parts.append(f"附近可见：{spot_objects}")
        if hooks:
            parts.append(f"可自然提到：{hooks}")
        return "；".join(parts)

    def _format_sensory_line(self, location: dict) -> str:
        """格式化地点的五感线索。"""
        if not location:
            return ""
        sensory = location.get("sensory") or {}
        pairs = [
            ("看见", sensory.get("sight")),
            ("听见", sensory.get("sound")),
            ("闻到", sensory.get("smell")),
            ("触感", sensory.get("touch")),
        ]
        texts = [f"{label}：{value}" for label, value in pairs if str(value or "").strip()]
        return "；".join(texts)

    def _format_objects_line(self, location: dict, zone_id: str, spot_id: str) -> str:
        """格式化当前地点自然存在的物品与道具。"""
        objects: list[str] = []
        if location:
            objects.extend(str(item).strip() for item in location.get("visible_objects", []) if str(item).strip())
            spot_data = (location.get("spot_perception") or {}).get(spot_id, {})
            objects.extend(str(item).strip() for item in spot_data.get("visible_objects", []) if str(item).strip())

        item_lines = self._matching_item_lines(zone_id, spot_id)
        compact_objects = self._dedupe(objects)[:6]
        parts = []
        if compact_objects:
            parts.append("可见物：" + "、".join(compact_objects))
        if item_lines:
            parts.append("相关物品：" + "；".join(item_lines[:3]))
        return "；".join(parts)

    def _format_people_lines(self, participant_ids: list[str]) -> list[str]:
        """格式化当前对话人物的视觉、存在感和称呼建议。"""
        lines: list[str] = []
        for participant_id in self._dedupe(participant_ids):
            profile = self._load_person_profile(participant_id)
            if not profile:
                continue
            name = get_player_profile_label() if participant_id == "player" else profile.get("name", participant_id)
            gender = self._gender_label(profile.get("gender", "unknown"))
            tags = self._join(profile.get("visual_tags"))
            presence = self._join(profile.get("presence_tags"))
            speech = render_player_tokens(str(profile.get("speech_perception", "")).strip())
            address = render_player_tokens(str(profile.get("address_hint", "")).strip())
            parts = [f"- {name}：{gender}", str(profile.get("occupation", "")).strip()]
            if tags:
                parts.append(f"视觉={tags}")
            if presence:
                parts.append(f"存在感={presence}")
            if speech:
                parts.append(f"说话感={speech}")
            if address:
                parts.append(f"称呼建议={address}")
            lines.append("；".join(part for part in parts if part))
        return lines

    def _matching_item_lines(self, zone_id: str, spot_id: str) -> list[str]:
        """按地点来源挑选少量相关物品感知。"""
        matches: list[str] = []
        for item in self._load_items():
            source = str(item.get("source", ""))
            if not self._item_matches_location(source, zone_id, spot_id):
                continue
            name = item.get("name", item.get("id", "物品"))
            tags = self._join(item.get("perception_tags"))
            presence = str(item.get("presence", "")).strip()
            sensory = item.get("sensory") or {}
            sensory_text = self._join([sensory.get("sight"), sensory.get("smell")])
            details = self._shorten(self._join([tags, presence, sensory_text]), 72)
            matches.append(f"{name}（{details}）" if details else str(name))
        return matches

    @staticmethod
    def _item_matches_location(source: str, zone_id: str, spot_id: str) -> bool:
        """判断物品来源是否适合当前地点。"""
        if source == zone_id:
            return True
        if source == "vending" and zone_id == "street" and spot_id == "vending_machine":
            return True
        if source == "shop" and zone_id in {"player_cafe", "wagashi"}:
            return True
        if source == "found" and zone_id in {"park", "riverside"}:
            return True
        if source == "sakura_gift" and zone_id in {"flower_shop", "player_cafe"}:
            return True
        return False

    def _load_person_profile(self, participant_id: str) -> dict:
        """读取 NPC 或玩家 profile。"""
        if participant_id == "player":
            return self._load_player_profile()
        if participant_id in self._npc_cache:
            return self._npc_cache[participant_id]
        path = self.profiles_dir / f"{participant_id}.json"
        data = self._load_json(path)
        self._npc_cache[participant_id] = data
        return data

    def _load_player_profile(self) -> dict:
        """读取玩家感知 profile。"""
        if self._player_cache is None:
            self._player_cache = self._load_json(self.player_profile_path)
        return self._player_cache

    def _load_location(self, zone_id: str) -> dict:
        """读取地点 profile。"""
        if zone_id in self._location_cache:
            return self._location_cache[zone_id]
        data = self._load_json(self.location_profiles_dir / f"{zone_id}.json")
        self._location_cache[zone_id] = data
        return data

    def _load_items(self) -> list[dict]:
        """读取共享物品配置。"""
        if self._items_cache is None:
            data = self._load_json(self.items_path)
            self._items_cache = data.get("items", []) if isinstance(data, dict) else []
        return self._items_cache

    @staticmethod
    def _load_json(path: Path) -> dict:
        """读取 JSON 文件，缺失时返回空配置。"""
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _split_location(location_id: str) -> tuple[str, str]:
        """拆分 zone.spot 格式地点 ID。"""
        if "." in (location_id or ""):
            zone_id, spot_id = location_id.split(".", 1)
            return zone_id, spot_id
        return location_id or "street", ""

    @staticmethod
    def _time_key(game_time: str) -> str:
        """把游戏时间粗略映射到地点时段氛围。"""
        digits = []
        for ch in game_time or "":
            if ch.isdigit():
                digits.append(ch)
            elif digits:
                break
        hour = 12
        if " " in (game_time or ""):
            after_space = game_time.split(" ", 1)[1]
            hour_digits = []
            for ch in after_space:
                if ch.isdigit():
                    hour_digits.append(ch)
                elif hour_digits:
                    break
            if hour_digits:
                hour = int("".join(hour_digits))
        if 5 <= hour < 11:
            return "morning"
        if 11 <= hour < 16:
            return "noon"
        if 16 <= hour < 20:
            return "evening"
        return "night"

    @staticmethod
    def _gender_label(gender: str) -> str:
        """把 profile 性别字段转为中文标签。"""
        return {
            "male": "男性",
            "female": "女性",
            "nonbinary": "非二元",
            "unknown": "未知",
        }.get(str(gender).strip().lower(), str(gender or "未知"))

    @staticmethod
    def _join(value) -> str:
        """把字符串或列表整理成短文本。"""
        if isinstance(value, list):
            return "、".join(str(item).strip() for item in value if str(item or "").strip())
        return str(value or "").strip()

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        """保持顺序去重。"""
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    @staticmethod
    def _shorten(text: str, limit: int) -> str:
        """压缩感知片段长度，避免 prompt 被物品描述撑大。"""
        clean = str(text or "").strip()
        if len(clean) <= limit:
            return clean
        return clean[:limit].rstrip("，。！？、,.!? ") + "..."
