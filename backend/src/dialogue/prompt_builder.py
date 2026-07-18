"""
对话 Prompt 组装 — System Prompt + 短期记忆 + 图检索上下文。
"""
import json
import logging
from pathlib import Path

from .perception_context import PerceptionContextBuilder
from .player_name import get_player_display_name, render_player_tokens
from ..world.location_state import is_transit_location
from ..prompting import PromptAssembler
from ..prompting.tag_formatter import format_npc

logger = logging.getLogger("sakurabashi.prompt")


# 角色名映射
NPC_NAMES = {
    "sakura": "鹿岛樱", "chihaya": "千早",
    "kazuha": "和叶", "tatsunosuke": "龙之介", "kujo": "九条莲",
}

# 地点 ID → 中文名
LOC_LABELS = {
    "player_cafe": "喫茶店", "flower_shop": "花店", "bakery": "面包店",
    "bookstore": "旧书店", "wagashi": "和果子店", "police_box": "派出所",
    "street": "商店街", "park": "公园", "riverside": "河边",
}
SPOT_LABELS = {
    "counter": "柜台", "doorway": "门口", "back_room": "后台",
    "window_seat": "窗边", "reading_sofa": "读书沙发", "kneading_table": "揉面台",
    "bench_01": "长椅", "bench_02": "长椅", "bench_outside": "门外长椅",
    "desk": "桌前", "window_chair": "窗边椅子", "back_workbench": "后台工作台",
    "window_display": "橱窗", "display_shelf": "展示架", "display_case": "展示柜",
    "oven_area": "烤箱区", "workbench": "工作台", "cherry_tree": "樱花树",
    "fountain": "喷泉", "crossroad": "路口", "arcade": "拱廊",
    "vending_machine": "自动贩卖机", "bulletin_board": "公告栏",
    "entrance": "入口", "grass_area": "草地", "bridge": "桥",
    "cherry_row": "樱花道", "path": "小路", "kitchen": "厨房",
    "table_01": "桌子", "table_02": "桌子",
    "bookshelf_mystery": "推理书架", "bookshelf_literature": "文学书架",
}

# 行为 ID → 中文名
ACTION_LABELS = {
    "stand": "站着", "patrol": "巡逻", "visit": "拜访", "sleep": "睡觉",
    "work_open": "开店", "work_close": "关店", "work_craft": "制作",
    "work_tend": "打理", "work_arrange": "整理", "work_clean": "打扫",
    "eat": "吃饭", "drink": "喝茶", "rest": "休息",
    "read": "看书", "browse": "闲逛", "stare_outside": "发呆看外面",
    "lean": "靠着", "sit": "坐下", "feed_cats": "喂猫",
    "greet": "打招呼", "talk": "聊天", "give_item": "送东西",
    "observe": "观察", "walk": "散步",
}

MEMORY_TIME_RULES = """# 记忆时间规则
- 近期记忆和相关回忆里的时间标签很重要：较新的记忆优先代表现在，较旧的记忆只代表当时知道的事。
- 如果旧记忆说“听说/准备/可能”，不要把它改写成亲眼所见或已经完成。
- 如果新记忆更新了旧说法，以新记忆为准；不确定时用“听说”“好像”“我还不清楚”。
"""

def _loc_name(location_id: str) -> str:
    """location_id → 中文名，如 flower_shop.counter → 花店柜台"""
    if "." in location_id:
        zone, spot = location_id.split(".", 1)
        z = LOC_LABELS.get(zone, zone)
        s = SPOT_LABELS.get(spot, spot)
        return f"{z}{s}"
    return LOC_LABELS.get(location_id, location_id)

def _act_name(action_id: str) -> str:
    """action_id → 中文名"""
    return ACTION_LABELS.get(action_id, action_id)


def _resolve_location_context(state: dict, fallback_location: str) -> tuple[str, str]:
    """解析 NPC 当前地点 ID 和给 Prompt 使用的位置描述。"""
    current_location = str(state.get("current_location") or fallback_location or "街上")
    is_moving = state.get("movement_status") == "moving" or is_transit_location(current_location)
    if not is_moving:
        return current_location, _loc_name(current_location)

    origin = str(state.get("movement_origin") or "未知地点")
    target = str(state.get("movement_target") or "未知地点")
    description = f"从{_loc_name(origin)}到{_loc_name(target)}的途中（移动中，不属于任何地区）"
    return current_location, description

def _parse_day(time_str: str) -> int:
    """"第1天 08:00" → 1, "Day 1, 08:00" → 1"""
    if not time_str:
        return 999
    import re
    m = re.search(r'(\d+)', time_str)
    return int(m.group(1)) if m else 999

def _time_cn(game_time: str) -> str:
    """保持中文格式（已由 clock.time_str() 直接输出中文）"""
    return game_time

# 默认 System Prompt 模板
SYSTEM_PROMPT_TEMPLATE = """# 角色
你是{name}，{age}岁，{gender}。
你是商店街「樱桥通」上{occupation}。

# 性格
{personality}

# 说话风格
{speech_style}

# 当前状态
时间：{game_time}
你在：{location}
正在：{current_action}
{plan}
情绪：{emotion}
精力：{energy}/100
{current_need_line}

{perception_context}

# 关于对方
你现在怎么看{target_name}：{impression_text}
和TA说话时：{speech_hint}

{memory_time_rules}

# 规则
1. 用口语化、自然的中文对话，符合你的说话风格
2. 回答一般不超过 80 字（除非在讲故事或对方追问）
3. 你的记忆不是完美的——不确定的事用"好像""应该是"
4. 情绪、语气和态度要与当前状态、对对方的印象一致——这是最重要的规则
5. 如果被问到不该知道的事就说不知道
6. 这是你第一次见到对方的话，要表现出合理的反应
7. 优先根据「现场感知」里当前能看见、听见、闻到的人和物来组织对白
{first_encounter_line}

# 近期记忆
{short_term_memories}

# 相关回忆
{retrieved_context}
"""

# NPC → NPC 对话 System Prompt 模板（轻量记忆版）
NPC_DIALOGUE_SYSTEM = """# 场景
你是商店街「樱桥通」上的两个店主，正在进行一次日常对话。

# 当前
时间：{game_time}
地点：{location_name}

{perception_context}

# {name_a}（{npc_a_id}）
正在: {action_a}
{plan_a}
性格：{personality_a}
说话风格：{speech_a}
对{name_b}的当前印象：{impression_a}
和TA说话时：{speech_hint_a}

# {name_b}（{npc_b_id}）
正在: {action_b}
{plan_b}
性格：{personality_b}
说话风格：{speech_b}
对{name_a}的当前印象：{impression_b}
和TA说话时：{speech_hint_b}

# 重要
对话内容必须和「正在做的事」一致——在开店就聊开店的事，在休息就聊日常，不要在柜台前说自己在河边散步。

{memory_time_rules}

{recent_memories}

{retrieved_a}
{retrieved_b}

# 规则
1. 生成 2-{turns} 轮日常对话（由你决定几轮），每轮一句。如果不想聊可以只回1-2轮
2. 格式：角色名: 对话内容（一行一句，使用中文冒号也可以接受）
3. 每句话控制在 80 字以内
4. 语气和态度要符合当下印象和状态——想接近时更自然，想回避时更克制
5. 对话内容要自然，可以是：天气/季节、商品/食材、当天小事、问候关心、商店街的事
6. 不要聊太私密的话题（除非当前印象明显亲近、信任）
7. 符合两人的性格和说话风格
8. 如果有「近期记忆」，自然地参考但不要太刻意
9. 优先根据「现场感知」里当前能看见、听见、闻到的人和物来组织对白
"""

class PromptBuilder:
    """对话 Prompt 组装器"""

    def __init__(self, db, profiles_dir: str, prompt_assembler: PromptAssembler | None = None):
        self.db = db
        self.profiles_dir = Path(profiles_dir)
        self._profile_cache: dict[str, dict] = {}
        self._retrieval = None
        self._plan_provider = None
        self._state_manager = None
        self._perception = PerceptionContextBuilder(self.profiles_dir)
        self.prompt_assembler = prompt_assembler or PromptAssembler()

    def _load_profile(self, npc_id: str) -> dict:
        """加载 NPC 配置（缓存）"""
        if npc_id in self._profile_cache:
            return self._profile_cache[npc_id]
        path = self.profiles_dir / f"{npc_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                profile = json.load(f)
        else:
            profile = {"name": npc_id, "age": 20, "gender": "unknown",
                       "occupation": "未知", "personality": "", "speech_style": ""}
        self._profile_cache[npc_id] = profile
        return profile

    def set_retrieval(self, engine):
        """设置检索引擎（Phase 5 注入）"""
        self._retrieval = engine

    def set_plan_provider(self, provider):
        """注入剩余计划摘要提供者，避免反向读取 main 全局。"""
        self._plan_provider = provider

    def set_state_manager(self, manager):
        """注入状态/印象读取器。"""
        self._state_manager = manager

    def build(self, npc_id: str, target_id: str = "player",
              game_time: str = "", location: str = "", turn_context=None) -> list[dict]:
        """
        构建对话 messages 列表。
        [system_prompt, ...short_term, user_message]
        """
        profile = self._load_profile(npc_id)

        # NPC 当前状态
        state = self._get_state(npc_id)
        if not state:
            state = {"emotion": "平静", "energy": 80, "current_need": None,
                     "is_first_encounter": 0, "current_location": location}

        impression = self._get_impression(npc_id, target_id)

        # 短期记忆（最近 PLAYER_MEMORY_DAYS 天）
        all_short = self.db.fetchall(
            """SELECT content, created_at_game_time FROM short_term_memories
               WHERE subject_id = ? ORDER BY created_at_game_time DESC LIMIT 20""",
            (npc_id,))
        current_day = _parse_day(game_time)
        short_term = [m for m in all_short
                      if current_day - _parse_day(m["created_at_game_time"]) < self.PLAYER_MEMORY_DAYS][:5]
        short_text = "\n".join(f"- {m['content']}" for m in short_term) if short_term else "（暂无近期记忆）"

        # 首遇标记
        is_first = state.get("is_first_encounter", 0)
        first_line = ""
        if is_first:
            target_name = self._get_target_name(target_id)
            first_line = (
                f"8. 这是开局后你第一次和{target_name}正式说话。"
                "按你的记忆判断熟悉程度；如果只是听说TA回来，不要说“好久不见”“一点都没变”这类亲眼确认过的寒暄。"

            )

        # 心事
        NEED_LABELS = {"hungry": "有点饿了", "tired": "有点累了", "social": "想和人说说话",
                       "bored": "觉得无聊"}
        need_line = ""
        if state.get("current_need"):
            cn = NEED_LABELS.get(state["current_need"], state["current_need"])
            need_line = f"今天心里在想：{cn}"
        if state.get("lingering_concern"):
            need_line = (need_line + "\n" if need_line else "") + f"另外还挂着：{state['lingering_concern']}"

        # 收集事实后交给 Prompt 数据层渲染，业务逻辑不再持有任务文案。
        resolved_location, location_text = _resolve_location_context(state, location)
        retrieved_context = (
            turn_context.retrieved_memories
            if turn_context is not None
            else self._get_retrieved_context(
                npc_id,
                target_id,
                resolved_location,
                game_time,
                mode="player_dialogue",
            )
        )
        participant_text = "（暂无参与者关系记录）"
        current_query = "（无）"
        conversation_summary = "（暂无）"
        if turn_context is not None:
            participant_text = "\n".join(
                f"- 对话对象 {item.target_id}: bond={item.bond:.2f}; {item.impression}"
                for item in turn_context.participant_impressions
            ) or participant_text
            current_query = turn_context.current_query
            conversation_summary = turn_context.conversation_summary or conversation_summary
        messages = self.prompt_assembler.build("player_dialogue", {
            "profile": profile,
            "name": profile.get("name", npc_id), "age": profile.get("age", "?"),
            "gender": profile.get("gender", ""), "occupation": profile.get("occupation", ""),
            "game_time": _time_cn(game_time),
            "location": location_text,
            "current_action": _act_name(state.get("current_action") or "stand"),
            "plan": self._get_remaining_plan(npc_id),
            "emotion": state.get("emotion", "平静"),
            "energy": state.get("energy", 80),
            "need_line": need_line,
            "perception_context": self._perception.build_player_dialogue(
                npc_id,
                target_id,
                resolved_location,
                game_time,
            ),
            "target_name": self._get_target_name(target_id),
            "impression_text": impression["text"],
            "speech_hint": impression["speech_hint"],
            "memory_time_rules": MEMORY_TIME_RULES,
            "first_encounter_line": first_line,
            "short_term_memories": short_text,
            "retrieved_context": retrieved_context,
            "current_query": current_query,
            "conversation_summary": conversation_summary,
            "participant_text": participant_text,
        })
        messages[0]["content"] = render_player_tokens(messages[0]["content"])
        return messages

    def _get_retrieved_context(self, npc_id: str, target_id: str, location: str,
                                game_time: str, limit: int = 5,
                                mode: str | None = None) -> str:
        """调用检索引擎获取相关记忆上下文。"""
        if self._retrieval is None:
            return ""
        try:
            ctx = self._retrieval.retrieve(npc_id, target_id, location, game_time, mode=mode)
            if not ctx:
                return ""
            if limit < 5:
                lines = ctx.split("\n")[:limit]
                return "\n".join(lines) if lines else ""
            return ctx
        except Exception as e:
            logger.warning(f"检索失败: {e}")
            return ""

    def _bond_description(self, bond: float) -> str:
        if bond >= 0.8:
            return "亲密信任"
        elif bond >= 0.6:
            return "喜欢且信任"
        elif bond >= 0.4:
            return "友好"
        elif bond >= 0.2:
            return "普通认识"
        elif bond >= 0.0:
            return "初识"
        else:
            return "疏远"

    def _get_target_name(self, target_id: str) -> str:
        """返回 prompt 中使用的目标显示名。"""
        if target_id == "player":
            return get_player_display_name()
        return NPC_NAMES.get(target_id, target_id)

    # ══════════════════════════════════════════════════════════
    # NPC → NPC 对话 Prompt（轻量记忆版）
    # ══════════════════════════════════════════════════════════

    # NPC 对话记忆参数（均低于玩家对话的数值）
    NPC_MEMORY_LIMIT = 4        # 短期记忆条数（玩家: 5）
    NPC_MEMORY_DAYS = 2          # NPC 对话只取今明两天
    PLAYER_MEMORY_DAYS = 3       # 玩家对话取最近 3 天
    NPC_MEMORY_IMPORTANCE = 0.3 # 记忆重要度（玩家对话: 0.5）

    def build_npc_to_npc(self, npc_a: str, npc_b: str,
                         location: str = "", game_time: str = "",
                         turns: int = 3) -> list[dict]:
        """构建 NPC 间对话的 messages。

        比 player-NPC prompt 轻量：
          - 只取 2 条近期短期记忆（玩家 5 条）
          - 无印象推导、无图检索（NPC 聊天不需要深层回忆）
          - 性格 + 关系 + 场景 + 轻量记忆

        Args:
            npc_a: 发起方 NPC ID
            npc_b: 目标方 NPC ID
            location: location_id（用于场景描述）
            game_time: 游戏时间字符串
            turns: 对话轮数

        Returns:
            [{"role": "system", "content": "..."}]
        """
        profile_a = self._load_profile(npc_a)
        profile_b = self._load_profile(npc_b)

        name_a = profile_a.get("name", npc_a)
        name_b = profile_b.get("name", npc_b)

        # Impression
        impression_a = self._get_impression(npc_a, npc_b)
        impression_b = self._get_impression(npc_b, npc_a)

        # 当前行为 + 今日剩余计划
        action_a, action_b = self._get_current_actions(npc_a, npc_b)
        plan_a = self._get_remaining_plan(npc_a)
        plan_b = self._get_remaining_plan(npc_b)

        # ── 轻量记忆 + 图检索 ──
        recent_memories = self._build_npc_dialogue_memories(npc_a, npc_b, game_time)
        # 双方各检索轻量多跳记忆（比玩家更浅）
        ctx_a = self._get_retrieved_context(
            npc_a,
            npc_b,
            location,
            game_time,
            limit=3,
            mode="npc_dialogue",
        )
        ctx_b = self._get_retrieved_context(
            npc_b,
            npc_a,
            location,
            game_time,
            limit=3,
            mode="npc_dialogue",
        )

        # 中文格式化
        time_cn = _time_cn(game_time)
        loc_cn = _loc_name(location)
        perception_context = self._perception.build_npc_dialogue(
            npc_a,
            npc_b,
            location,
            game_time,
        )

        # 仅提交结构化对话事实，Prompt 文案由数据层维护。
        messages = self.prompt_assembler.build("npc_dialogue", {
            "profile": profile_a,
            "game_time": time_cn,
            "location_name": loc_cn,
            "perception_context": perception_context,
            "name_a": name_a,
            "npc_a_id": npc_a,
            "action_a": action_a,
            "plan_a": plan_a,
            "npc_tags_a": format_npc(profile_a),
            "impression_a": impression_a["text"],
            "speech_hint_a": impression_a["speech_hint"],
            "name_b": name_b,
            "npc_b_id": npc_b,
            "action_b": action_b,
            "plan_b": plan_b,
            "npc_tags_b": format_npc(profile_b),
            "impression_b": impression_b["text"],
            "speech_hint_b": impression_b["speech_hint"],
            "memory_time_rules": MEMORY_TIME_RULES,
            "turns": turns,
            "recent_memories": recent_memories,
            "retrieved_a": ctx_a,
            "retrieved_b": ctx_b,
        })
        messages[0]["content"] = render_player_tokens(messages[0]["content"])
        return messages

    def build_player_reply_suggestions(
        self,
        npc_id: str,
        target_id: str = "player",
        npc_reply: str = "",
        dialogue_messages: list[dict] | None = None,
        player_memories: list[str] | None = None,
        game_time: str = "",
        location: str = "",
    ) -> list[dict]:
        """构建玩家建议回复的提示词。"""
        profile = self._load_profile(npc_id)
        npc_name = profile.get("name", npc_id)
        player_name = self._get_target_name(target_id)
        state = self._get_state(npc_id) or {}
        impression = self._get_impression(npc_id, target_id)

        condensed_lines: list[str] = []
        for message in (dialogue_messages or [])[-6:]:
            role = message.get("role")
            content = str(message.get("content", "")).strip()
            if not content:
                continue
            if role == "assistant":
                condensed_lines.append(f"{npc_name}: {content[:120]}")
            elif role == "user":
                condensed_lines.append(f"{player_name}: {content[:120]}")

        history_text = "\n".join(condensed_lines) if condensed_lines else "（这是刚开始的一段对话）"
        player_memory_text = self._format_player_reply_memories(player_memories)
        npc_profile_text = self._format_reply_npc_profile(npc_id, profile)
        resolved_location, location_text = _resolve_location_context(state, location)
        perception_context = self._perception.build_player_dialogue(
            npc_id,
            target_id,
            resolved_location,
            game_time,
        )
        messages = self.prompt_assembler.build("player_reply_suggestions", {
            "npc_name": npc_name, "player_name": player_name,
            "npc_tags": npc_profile_text, "dialogue": history_text,
            "npc_reply": npc_reply.strip(), "perception_context": perception_context,
            "relationship_from_npc": impression.get("text", ""),
            "npc_speech_hint": impression.get("speech_hint", "按自然日常口吻回应即可。"),
            "game_time": _time_cn(game_time), "location": location_text,
            "player_memory_text": player_memory_text,
        })
        messages[0]["content"] = render_player_tokens(messages[0]["content"])
        return messages

    def _format_reply_npc_profile(self, npc_id: str, profile: dict) -> str:
        """把 NPC 基础信息压成快捷回复建议可读取的一行角色标签。"""
        gender = self._gender_label(profile.get("gender", ""))
        visual_tags = self._join_profile_list(profile.get("visual_tags"))
        presence_tags = self._join_profile_list(profile.get("presence_tags"))
        speech_perception = str(profile.get("speech_perception", "")).strip()
        address_hint = str(profile.get("address_hint", "")).strip()
        parts = [
            f"名字={profile.get('name', npc_id)}",
            f"年龄={profile.get('age', '?')}",
            f"性别={gender}",
            f"身份={profile.get('occupation', '')}",
        ]
        if visual_tags:
            parts.append(f"视觉标签={visual_tags}")
        if presence_tags:
            parts.append(f"存在感={presence_tags}")
        if speech_perception:
            parts.append(f"说话感={speech_perception}")
        if address_hint:
            parts.append(f"称呼建议={address_hint}")
        return "；".join(part for part in parts if part)

    @staticmethod
    def _gender_label(gender: str) -> str:
        """把 profile 性别字段转成中文，降低回复建议误判概率。"""
        mapping = {
            "male": "男性",
            "female": "女性",
            "nonbinary": "非二元",
            "unknown": "未知",
        }
        return mapping.get(str(gender).strip().lower(), str(gender or "未知"))

    @staticmethod
    def _join_profile_list(value) -> str:
        """把 profile 中的列表字段整理成短标签串。"""
        if isinstance(value, list):
            return "、".join(str(item).strip() for item in value if str(item).strip())
        return str(value or "").strip()

    def _format_player_reply_memories(self, player_memories: list[str] | None) -> str:
        """将玩家向量记忆整理成建议回复可用的轻量上下文。"""
        if not player_memories:
            return "（暂无明显相关记忆）"

        lines: list[str] = []
        for memory in player_memories[:3]:
            text = str(memory or "").strip()
            if not text:
                continue
            compact = text.replace("\n", " ").replace("\r", " ")
            if len(compact) > 120:
                compact = compact[:120].rstrip("，。！？、,.!? ") + "..."
            lines.append(f"- {compact}")

        return "\n".join(lines) if lines else "（暂无明显相关记忆）"

    def _build_npc_dialogue_memories(self, npc_a: str, npc_b: str,
                                       game_time: str = "") -> str:
        """为 NPC 对话构建轻量记忆上下文（今天 + 昨天，2天内）。"""
        current_day = _parse_day(game_time)
        memories: dict[str, list[str]] = {}
        for npc_id in [npc_a, npc_b]:
            rows = self.db.fetchall(
                """SELECT content, created_at_game_time FROM short_term_memories
                   WHERE subject_id = ?
                   ORDER BY created_at_game_time DESC LIMIT 20""",
                (npc_id,))
            if rows:
                # 只取最近 NPC_MEMORY_DAYS 天内
                filtered = [r for r in rows
                            if current_day - _parse_day(r["created_at_game_time"]) < self.NPC_MEMORY_DAYS]
                memories[npc_id] = [r["content"] for r in filtered[:self.NPC_MEMORY_LIMIT]]

        if not memories:
            return ""

        # 构建紧凑的"共同记忆"描述
        lines = ["# 近期记忆（自然参考，不要太刻意）"]
        for npc_id, texts in memories.items():
            name = NPC_NAMES.get(npc_id, npc_id)
            for text in texts:
                # 截断过长记忆
                short = text[:120] + "..." if len(text) > 120 else text
                short = render_player_tokens(short)
                lines.append(f"- {name}记得: {short}")

        return "\n".join(lines)

    def _get_current_actions(self, npc_a: str, npc_b: str) -> tuple[str, str]:
        """查询两个 NPC 当前行为（用于对话 Prompt 上下文对齐）"""
        actions: dict[str, str] = {}
        for nid in (npc_a, npc_b):
            state = self.db.fetchone(
                """SELECT current_action, current_location, movement_origin,
                          movement_target, movement_status
                   FROM npc_states WHERE npc_id=?""",
                (nid,))
            if state:
                _, loc = _resolve_location_context(state, state.get("current_location", "?"))
                act = _act_name(state.get("current_action") or "stand")
                actions[nid] = f"{act}（{loc}）"
            else:
                actions[nid] = "待着"
        return actions.get(npc_a, "stand"), actions.get(npc_b, "stand")

    def _get_remaining_plan(self, npc_id: str) -> str:
        """获取 NPC 今日剩余计划（由外部 provider 注入）。"""
        if self._plan_provider:
            try:
                return self._plan_provider(npc_id)
            except Exception as e:
                logger.debug(f"剩余计划读取失败 ({npc_id}): {e}")
        return ""

    def _get_state(self, npc_id: str) -> dict | None:
        """统一读取 NPC 状态，优先走状态层。"""
        if self._state_manager and hasattr(self._state_manager, "get_state"):
            try:
                return self._state_manager.get_state(npc_id)
            except Exception as e:
                logger.debug(f"状态读取失败 ({npc_id}): {e}")
        return self.db.fetchone("SELECT * FROM npc_states WHERE npc_id = ?", (npc_id,))

    def _get_impression(self, owner_id: str, target_id: str) -> dict:
        """统一读取印象，缺失时回退到普通熟人判断。"""
        if self._state_manager and hasattr(self._state_manager, "get_impression_bundle"):
            try:
                return self._state_manager.get_impression_bundle(owner_id, target_id)
            except Exception as e:
                logger.debug(f"印象读取失败 ({owner_id}->{target_id}): {e}")
        target_name = self._get_target_name(target_id)
        return {
            "text": f"对{target_name}目前没有特别鲜明的判断。",
            "speech_hint": "先按平常语气交流。",
            "approach_bias": 0.0,
        }
