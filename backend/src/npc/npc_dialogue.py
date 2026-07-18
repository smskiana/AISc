"""
NPC → NPC 对话生成器。

由 BehaviorEngine 的社交检测触发，通过 LLM 生成 2-4 轮简短对话，
逐句发送 NPC_BUBBLE 消息到 Unity。对话结束后写入短期记忆。

对话轮数和单句长度由 Prompt 软约束，调用层不设置硬 token 上限。
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import uuid

from ..dialogue.player_name import get_player_name_candidates, render_player_tokens

logger = logging.getLogger("sakurabashi.npc_dialogue")

# ── 可配置常量 ──
NPC_TURNS_MIN = 2
NPC_TURNS_MAX = 8           # 放宽上限，LLM 自己决定几轮
NPC_DIALOGUE_TEMPERATURE = 0.85
NPC_DIALOGUE_API_TIMEOUT = 15.0    # API 超时（秒）
BUBBLE_DELAY_BETWEEN_TURNS = 0.5   # 两句气泡之间的延迟（秒）
PLAYER_FACT_GUARD_FALLBACK_TEMPLATE = "听说{player_nickname}准备重新开奶奶留下的喫茶店，不过具体进展我还没确认。"
UNCERTAIN_MEMORY_MARKERS = ("听说", "好像", "似乎", "可能", "准备", "打算", "还不清楚", "不确定")


def _player_alias_pattern() -> str:
    """生成玩家称呼的正则片段，跟随当前昵称变化。"""
    return "|".join(re.escape(name) for name in get_player_name_candidates())


def _unverified_player_action_re() -> re.Pattern:
    """构建未验证玩家行为的宽松识别正则。"""
    aliases = _player_alias_pattern()
    return re.compile(
        rf"(?:看到|看见|路过|碰到|遇见).{{0,20}}(?:{aliases}).{{0,20}}(?:搬|箱子|收拾|整理|打扫|修|贴|挂|安装|装修|招牌)"
        rf"|(?:{aliases}).{{0,20}}(?:搬|箱子|收拾|整理|打扫|修|贴|挂|安装|装修|招牌)"
        rf"|(?:帮|陪).{{0,10}}(?:{aliases}).{{0,20}}(?:搬|箱子|收拾|整理|打扫|修|贴|挂|安装|装修)"
    )


def _direct_player_action_claim_re() -> re.Pattern:
    """构建亲历式玩家行动断言识别正则。"""
    aliases = _player_alias_pattern()
    return re.compile(
        rf"(?:看到|看见|路过|碰到|遇见).{{0,20}}(?:{aliases}).{{0,20}}(?:搬|箱子|收拾|整理|打扫|修|贴|挂|安装|装修|招牌)"
        rf"|(?:帮|陪).{{0,10}}(?:{aliases}).{{0,20}}(?:搬|箱子|收拾|整理|打扫|修|贴|挂|安装|装修)"
        r"|(?:看到|看见|路过|碰到|遇见).{0,20}(?:他|她).{0,20}(?:搬|箱子|桌子|桌椅|收拾|整理|打扫|修|贴|挂|安装|装修).{0,20}(?:开店|开起来|喫茶店|咖啡店)"
    )


class NpcDialogueManager:
    """NPC 间对话生成管理器。

    使用方式:
      1. 在 main.py lifespan 中创建实例
      2. 调用 behavior.set_npc_dialogue_callback(dialogue_mgr.on_social_trigger)
      3. BehaviorEngine 检测到社交机会 → 回调 → 生成对话 → 发送气泡
    """

    def __init__(self, prompt_builder, ws_sender: callable, db=None, state_mgr=None):
        self.prompt_builder = prompt_builder
        self._ws_sender = ws_sender
        self._db = db  # SQLiteClient，用于写入短期记忆
        self._state_mgr = state_mgr

        # 活跃对话防并发: {("npc_a", "npc_b")}
        self._active: set[tuple[str, str]] = set()

    # ══════════════════════════════════════════════════════════
    # 主入口 — BehaviorEngine 回调
    # ══════════════════════════════════════════════════════════

    async def on_social_trigger(self, npc_a: str, npc_b: str,
                                 location: str, game_time: str = "") -> None:
        """BehaviorEngine 回调：检测到社交机会时调用。

        Args:
            npc_a: 发起方 NPC ID
            npc_b: 目标方 NPC ID
            location: 当前 location_id（用于场景描述）
            game_time: 游戏时间字符串（用于记忆写入）
        """
        pair = tuple(sorted([npc_a, npc_b]))  # type: ignore
        if pair in self._active:
            logger.debug(f"对话进行中，跳过: {npc_a} ↔ {npc_b}")
            return

        # 任一 NPC 已在其他对话中 → 跳过（不支持多人同时对话）
        if self.is_npc_busy(npc_a) or self.is_npc_busy(npc_b):
            logger.debug(f"NPC 正忙，跳过: {npc_a} ↔ {npc_b}")
            return

        self._active.add(pair)
        try:
            await self._generate_and_send(npc_a, npc_b, location, game_time)
        except Exception as e:
            logger.error(f"NPC 对话生成失败 ({npc_a}-{npc_b}): {e}")
        finally:
            self._active.discard(pair)

    def is_npc_busy(self, npc_id: str) -> bool:
        """检查 NPC 是否正在参与任何对话。"""
        for a, b in self._active:
            if npc_id in (a, b):
                return True
        return False

    async def generate_prepared_social(
        self,
        request_id: str,
        npc_a: str,
        npc_b: str,
        location: str,
        game_time: str = "",
    ) -> list[tuple[str, str]]:
        """在 Unity 会合后生成结构化内容，但不发送、不写入记忆。"""
        from ..dialogue import llm_client as llm_module

        try:
            messages = self.prompt_builder.build_npc_to_npc(npc_a, npc_b, location, game_time)
            raw = await llm_module.llm_client.chat_async(
                messages,
                temperature=NPC_DIALOGUE_TEMPERATURE,
            )
            lines = self._sanitize_player_fact_claims(
                self._parse_dialogue(raw or "", npc_a, npc_b), npc_a, npc_b
            )
        except Exception as error:
            logger.error(f"LLM API 调用失败 ({npc_a}-{npc_b}): {error}")
            lines = self._build_fallback_lines(npc_a, npc_b)

        return lines[:NPC_TURNS_MAX]

    def commit_prepared_social(
        self,
        npc_a: str,
        npc_b: str,
        lines: list[tuple[str, str]],
        location: str,
        game_time: str,
        base_world_revision: int = 0,
        operation_id: str = "",
    ) -> dict:
        """在 Unity COMPLETE 后提交短期记忆，并返回双方运行时 effect。"""
        if self._db and game_time:
            self._save_dialogue_memory(npc_a, npc_b, lines, location, game_time)
        summaries = self._build_interaction_summaries(npc_a, npc_b, lines) if lines else ("", "")
        effects = []
        if self._state_mgr and lines:
            summary_a, summary_b = summaries
            effect_a = self._state_mgr.apply_interaction_effect(
                npc_a, npc_b, summary_a, source="npc_dialogue",
                base_world_revision=base_world_revision,
                operation_id=f"{operation_id}:state:{npc_a}" if operation_id else "",
            )
            effect_b = self._state_mgr.apply_interaction_effect(
                npc_b, npc_a, summary_b, source="npc_dialogue",
                base_world_revision=base_world_revision,
                operation_id=f"{operation_id}:state:{npc_b}" if operation_id else "",
            )
            effects = [effect for effect in (effect_a, effect_b) if effect]
        return {
            "summary": " / ".join(part for part in summaries if part),
            "effects": effects,
        }

    async def _send_prepared_bubble(
        self,
        request_id: str,
        npc_id: str,
        text: str,
        target_npc_id: str,
        line_index: int,
        line_count: int,
    ) -> None:
        """发送关联社交 request_id 的单句气泡。"""
        duration = max(2.0, len(text) * 0.15)
        if self._ws_sender:
            await self._ws_sender({
                "type": "NPC_BUBBLE",
                "request_id": request_id,
                "npc_id": npc_id,
                "target_npc_id": target_npc_id,
                "text": text,
                "duration_sec": round(duration, 1),
                "style": "speech",
                "line_index": line_index,
                "line_count": line_count,
            })

    def _build_fallback_lines(self, npc_a: str, npc_b: str) -> list[tuple[str, str]]:
        """构造无需 LLM 的两句关联对话回退内容。"""
        profile_a = self.prompt_builder._load_profile(npc_a)
        profile_b = self.prompt_builder._load_profile(npc_b)
        return [
            (npc_a, f"（{profile_a.get('name', npc_a)}向{profile_b.get('name', npc_b)}打招呼）"),
            (npc_b, f"（{profile_b.get('name', npc_b)}回应了{profile_a.get('name', npc_a)}）"),
        ]

    # ══════════════════════════════════════════════════════════
    # 对话生成
    # ══════════════════════════════════════════════════════════

    async def _generate_and_send(self, npc_a: str, npc_b: str,
                                  location: str, game_time: str = "") -> None:
        """生成完整对话 → 逐句发送气泡 → 写入短期记忆。"""
        from ..dialogue import llm_client as llm_module

        # 构建 Prompt
        messages = self.prompt_builder.build_npc_to_npc(npc_a, npc_b, location, game_time)

        # 调用 LLM（非流式，一次返回完整对话）
        try:
            raw = await llm_module.llm_client.chat_async(
                messages,
                temperature=NPC_DIALOGUE_TEMPERATURE,
            )
        except Exception as e:
            logger.error(f"LLM API 调用失败 ({npc_a}-{npc_b}): {e}")
            await self._send_fallback_bubbles(npc_a, npc_b)
            return

        if not raw:
            logger.warning(f"LLM 返回空 ({npc_a}-{npc_b})")
            return

        logger.debug(f"LLM 对话原文 ({npc_a}-{npc_b}):\n{raw}")

        # 解析对话
        lines = self._parse_dialogue(raw, npc_a, npc_b)
        lines = self._sanitize_player_fact_claims(lines, npc_a, npc_b)

        if not lines:
            logger.warning(f"对话解析为空 ({npc_a}-{npc_b})")
            return

        # 逐句发送气泡
        for speaker_id, text in lines[:NPC_TURNS_MAX]:
            target_id = npc_b if speaker_id == npc_a else npc_a
            await self._send_bubble(speaker_id, text, target_id)
            await asyncio.sleep(BUBBLE_DELAY_BETWEEN_TURNS)

        # ── 写入短期记忆（双方各一条） ──
        if self._db and game_time:
            self._save_dialogue_memory(npc_a, npc_b, lines, location, game_time)
        if self._state_mgr and lines:
            summary_a, summary_b = self._build_interaction_summaries(npc_a, npc_b, lines)
            self._state_mgr.apply_interaction_effect(npc_a, npc_b, summary_a, source="npc_dialogue")
            self._state_mgr.apply_interaction_effect(npc_b, npc_a, summary_b, source="npc_dialogue")

    # ══════════════════════════════════════════════════════════
    # 解析
    # ══════════════════════════════════════════════════════════

    def _parse_dialogue(self, raw: str, npc_a: str, npc_b: str) -> list[tuple[str, str]]:
        """解析 LLM 输出为 [(speaker_id, text), ...]。

        支持格式:
          - 鹿岛樱: 今天天气真好呢。
          - 千早: 是啊，面包都发得特别好！
          - sakura: 今天天气真好呢。（如果 LLM 用了 ID）

        也支持无冒号的行（直接跳过）。
        """
        name_to_id: dict[str, str] = {}
        # 收集 NPC 的名字映射
        for npc_id in [npc_a, npc_b]:
            profile = self.prompt_builder._load_profile(npc_id)
            name_to_id[profile.get("name", npc_id)] = npc_id
            name_to_id[npc_id] = npc_id  # LLM 可能直接用 ID

        results: list[tuple[str, str]] = []
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line or ":" not in line and "：" not in line:
                continue

            # 支持半角和全角冒号
            for sep in (":", "："):
                if sep in line:
                    parts = line.split(sep, 1)
                    break
            else:
                continue

            name_part = parts[0].strip().strip("「」『』\"\"''*#- ")
            text = parts[1].strip().strip("「」『』\"\"'' ")

            if not name_part or not text:
                continue

            # 查找 speaker ID
            speaker_id = name_to_id.get(name_part)
            if speaker_id is None:
                # 模糊匹配
                for known_name, known_id in name_to_id.items():
                    if known_name in name_part or name_part in known_name:
                        speaker_id = known_id
                        break
            if speaker_id is None:
                # 跳过无法识别的行
                logger.debug(f"无法识别发言者: {name_part}")
                continue

            results.append((speaker_id, text))

        return results

    def _sanitize_player_fact_claims(self, lines: list[tuple[str, str]],
                                     npc_a: str, npc_b: str) -> list[tuple[str, str]]:
        """守住玩家事实边界，避免 NPC 把未发生的玩家行为写进对白和记忆。"""
        sanitized: list[tuple[str, str]] = []
        for speaker_id, text in lines:
            if self._looks_like_unverified_player_action(text):
                logger.warning(
                    "[FACT_GUARD] npc_dialogue_player_claim sanitized pair=%s-%s speaker=%s text=%s",
                    npc_a,
                    npc_b,
                    speaker_id,
                    text,
                )
                sanitized.append((speaker_id, render_player_tokens(PLAYER_FACT_GUARD_FALLBACK_TEMPLATE)))
            else:
                sanitized.append((speaker_id, text))
        return sanitized

    @staticmethod
    def _looks_like_unverified_player_action(text: str) -> bool:
        """仅拦截亲历式玩家行动断言；带传闻/不确定语气的内容交给时间记忆判断。"""
        if _direct_player_action_claim_re().search(text):
            return True
        if any(marker in text for marker in UNCERTAIN_MEMORY_MARKERS):
            return False
        return bool(_unverified_player_action_re().search(text))

    # ══════════════════════════════════════════════════════════
    # 发送
    # ══════════════════════════════════════════════════════════

    async def _send_bubble(self, npc_id: str, text: str,
                            target_npc_id: str) -> None:
        """发送单句 NPC_BUBBLE 消息到 Unity。"""
        # 根据文本长度估算显示时长
        duration = max(2.0, len(text) * 0.15)

        cmd = {
            "type": "NPC_BUBBLE",
            "npc_id": npc_id,
            "target_npc_id": target_npc_id,
            "text": text,
            "duration_sec": round(duration, 1),
            "style": "speech",
        }

        if self._ws_sender:
            await self._ws_sender(cmd)

        logger.debug(f"气泡: {npc_id} → {target_npc_id}: {text[:50]}...")

    def _save_dialogue_memory(self, npc_a: str, npc_b: str,
                               lines: list[tuple[str, str]],
                               location: str, game_time: str) -> None:
        """将对话内容写入双方 NPC 的短期记忆。
        包含时间、地点、情绪基调，方便后续对话接上上下文。
        """
        # 各方视角
        lines_a, lines_b = [], []
        for speaker_id, text in lines:
            if speaker_id == npc_a:
                lines_a.append(f"我: {text}")
                lines_b.append(f"对方: {text}")
            else:
                lines_a.append(f"对方: {text}")
                lines_b.append(f"我: {text}")

        # 格式化：时间 + 地点 + 对话原文
        zone = location.split(".")[0] if "." in location else location
        content_a = f"[{game_time} @ {zone}]\n" + "\n".join(lines_a)
        content_b = f"[{game_time} @ {zone}]\n" + "\n".join(lines_b)

        participants = json.dumps([npc_a, npc_b], ensure_ascii=False)

        try:
            for npc_id, content in [(npc_a, content_a), (npc_b, content_b)]:
                self._db.execute(
                    """INSERT INTO short_term_memories
                       (id, subject_id, type, content, importance,
                        emotional_valence, location, participants,
                        created_at_game_time)
                       VALUES (?, ?, 'dialogue', ?, 0.3, 0.0, ?, ?, ?)""",
                    (f"stm_{uuid.uuid4().hex[:8]}", npc_id, content,
                     zone, participants, game_time),
                )
            logger.debug(f"对话记忆已保存: {npc_a} ↔ {npc_b} "
                         f"({len(lines)} 轮) @ {game_time}")
        except Exception as e:
            logger.error(f"保存对话记忆失败 ({npc_a}-{npc_b}): {e}")

    def _build_interaction_summaries(self, npc_a: str, npc_b: str,
                                     lines: list[tuple[str, str]]) -> tuple[str, str]:
        """将一段 NPC 对话压缩成双方各自的白天即时印象变化摘要。"""
        def _name(npc_id: str) -> str:
            profile = self.prompt_builder._load_profile(npc_id)
            return profile.get("name", npc_id)

        name_a = _name(npc_a)
        name_b = _name(npc_b)
        text_lines = []
        for speaker_id, text in lines[:4]:
            speaker = name_a if speaker_id == npc_a else name_b
            text_lines.append(f"{speaker}：{text}")
        merged = " / ".join(text_lines)[:180]
        return (
            f"刚和{name_b}聊过。{merged}",
            f"刚和{name_a}聊过。{merged}",
        )

    async def _send_fallback_bubbles(self, npc_a: str, npc_b: str) -> None:
        """LLM 不可用时的占位对话。"""
        profile_a = self.prompt_builder._load_profile(npc_a)
        profile_b = self.prompt_builder._load_profile(npc_b)
        name_a = profile_a.get("name", npc_a)
        name_b = profile_b.get("name", npc_b)

        lines = [
            (npc_a, npc_b, f"（{name_a}向{name_b}打招呼）"),
            (npc_b, npc_a, f"（{name_b}回应了{name_a}）"),
        ]
        for speaker, target, text in lines:
            await self._send_bubble(speaker, text, target)
            await asyncio.sleep(BUBBLE_DELAY_BETWEEN_TURNS)
