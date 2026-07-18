"""玩家对话会话服务。"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from typing import Any

from ..dialogue import llm_client as llm_module
from ..dialogue.conversation_context import ConversationTurn, ConversationTurnRequest
from ..dialogue.player_name import render_player_tokens_in_messages
from ..dialogue.reply_suggestion_diagnostics import ReplySuggestionTraceStore, reply_suggestion_trace_store
from ..memory.embedding import encode_batch
from .operation_context import GameTimeSnapshot

logger = logging.getLogger("sakurabashi.dialogue_service")

PLAYER_REPLY_SUGGESTION_CONTEXT_KEYS = [
    "npc_name", "player_name", "npc_tags", "dialogue", "npc_reply",
    "perception_context", "relationship_from_npc", "npc_speech_hint",
    "player_memory_text", "game_time", "location",
]


class PlayerDialogueService:
    """管理玩家与 NPC 的对话会话、总结与玩家记忆提取。"""

    def __init__(
        self,
        prompt_builder,
        sqlite,
        vector_store,
        state_mgr=None,
        conversation_memory=None,
        reply_suggestion_traces: ReplySuggestionTraceStore | None = None,
        schedule_replan_context_sender=None,
    ):
        """绑定对话生命周期依赖和逐轮会话记忆协调器。"""
        self.prompt_builder = prompt_builder
        self.sqlite = sqlite
        self.vector_store = vector_store
        self.state_mgr = state_mgr
        self.conversation_memory = conversation_memory
        self.reply_suggestion_traces = reply_suggestion_traces or reply_suggestion_trace_store
        self.schedule_replan_context_sender = schedule_replan_context_sender
        self._active_dialogues: dict[str, dict] = {}
        self._prepared_dialogues: dict[str, dict] = {}

    def reset_transient_state(self) -> None:
        """断线或读档时清理不可持久恢复的对话状态。"""
        self._prepared_dialogues.clear()
        self._active_dialogues.clear()
        if self.conversation_memory:
            self.conversation_memory.reset()

    async def prepare_dialogue(self, ws: Any, msg: dict) -> None:
        """登记玩家对话准备请求，并等待 Unity 确认现场已经就绪。"""
        request_id = str(msg.get("request_id") or f"dialogue_{uuid.uuid4().hex}")
        npc_id = str(msg.get("npc_id") or "")
        if not npc_id:
            await ws.send_json({
                "type": "GAME_ERROR",
                "request_id": request_id,
                "message": "缺少 npc_id",
            })
            return

        frozen_time = GameTimeSnapshot.from_dict(msg.get("game_time") or {})
        self._prepared_dialogues[request_id] = dict(
            msg,
            request_id=request_id,
            frozen_game_time=frozen_time,
        )
        await ws.send_json({
            "type": "DIALOGUE_PREPARED",
            "request_id": request_id,
            "npc_id": npc_id,
        })

    async def start_ready_dialogue(self, ws: Any, msg: dict) -> None:
        """收到 Unity 就绪确认后建立正式会话并生成首轮对话。"""
        request_id = str(msg.get("request_id") or "")
        prepared = self._prepared_dialogues.pop(request_id, None)
        if not prepared:
            await ws.send_json({
                "type": "GAME_ERROR",
                "request_id": request_id,
                "message": "对话准备请求不存在或已过期",
            })
            return

        prepared.update({key: value for key, value in msg.items() if value is not None})
        await self._start_dialogue_content(ws, prepared)

    async def _start_dialogue_content(self, ws: Any, msg: dict) -> None:
        """使用已确认的最新现场数据建立会话并流式生成首轮内容。"""
        request_id = str(msg.get("request_id") or "")
        npc_id = msg.get("npc_id", "")
        target = msg.get("target_id", "player")
        location = msg.get("player_location", "街上")
        frozen_time = msg.get("frozen_game_time")
        if not isinstance(frozen_time, GameTimeSnapshot):
            frozen_time = GameTimeSnapshot.from_dict(msg.get("game_time") or {})
        game_time_label = frozen_time.time_label()

        logger.info(f"对话开始: {npc_id} ← {target} @ {location}")

        try:
            if self.conversation_memory:
                self.conversation_memory.start(request_id, [npc_id, target], game_time_label)
                opening_turn = ConversationTurn("player", "（玩家走到了你面前。）")
                self.conversation_memory.append_turn(request_id, opening_turn)
                turn_context = self.conversation_memory.prepare_turn_context(ConversationTurnRequest(
                    conversation_id=request_id,
                    speaker_id=npc_id,
                    listener_ids=[target],
                    utterance=opening_turn.text,
                    location_id=location,
                    game_time=game_time_label,
                    mode="player_dialogue",
                ))
                await self._send_retrieval_diagnostic(ws, request_id, npc_id)
            else:
                turn_context = None
            system_msgs = self.prompt_builder.build(
                npc_id,
                target,
                game_time=game_time_label,
                location=location,
                turn_context=turn_context,
            )
        except Exception as e:
            logger.error(f"Prompt 构建失败: {e}")
            await ws.send_json({"type": "GAME_ERROR", "message": f"NPC 配置错误: {e}"})
            return

        messages = list(system_msgs)
        visual_context = self._format_visual_context(msg.get("visual_context"))
        if visual_context:
            messages.append({"role": "system", "content": visual_context})
        messages.append({
            "role": "user",
            "content": "（玩家走到了你面前。）",
        })
        messages = render_player_tokens_in_messages(messages)
        self._active_dialogues[npc_id] = {
            "request_id": request_id,
            "messages": messages,
            "target": target,
            "location": location,
            "visual_context": visual_context,
            "game_time": game_time_label,
            "game_day": frozen_time.day,
            "time_revision": frozen_time.time_revision,
        }
        pause_reason = self._dialogue_pause_reason(npc_id)

        started = time.perf_counter()
        full_text = ""
        try:
            stream = llm_module.llm_client.chat_stream_async(messages, temperature=0.85)
            async for token in stream:
                active = self._active_dialogues.get(npc_id)
                if not active or active.get("request_id") != request_id:
                    logger.info("对话生成已取消: npc=%s request=%s", npc_id, request_id)
                    return
                full_text += token
                await ws.send_json({
                    "type": "DIALOGUE_TOKEN",
                    "npc_id": npc_id,
                    "token": token,
                    "is_complete": False,
                })
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            full_text = "（抱歉，我有点走神了...）"
            await ws.send_json({
                "type": "DIALOGUE_TOKEN",
                "npc_id": npc_id,
                "token": full_text,
                "is_complete": True,
            })
            self._active_dialogues.pop(npc_id, None)
            if self.conversation_memory:
                self.conversation_memory.release(request_id)
            await ws.send_json({"type": "DIALOGUE_CLOSE", "npc_id": npc_id, "reason": "llm_error"})
            return

        active = self._active_dialogues.get(npc_id)
        if not active or active.get("request_id") != request_id:
            return
        active["messages"].append({"role": "assistant", "content": full_text})
        if self.conversation_memory:
            self.conversation_memory.append_turn(request_id, ConversationTurn(npc_id, full_text))
        logger.info(
            "[PERF] player_dialogue_reply npc=%s elapsed=%.2fs chars=%s",
            npc_id,
            time.perf_counter() - started,
            len(full_text),
        )
        await ws.send_json({
            "type": "DIALOGUE_COMPLETE",
            "npc_id": npc_id,
            "npc_text_complete": full_text,
            "choices": [],
        })
        self._schedule_player_reply_choices(ws, npc_id, active, full_text)

    async def handle_player_choice(self, ws: Any, msg: dict) -> None:
        """玩家选择对话选项，继续对话。"""
        npc_id = msg.get("npc_id", "")
        choice_text = msg.get("choice_text", "")

        if npc_id not in self._active_dialogues:
            await ws.send_json({"type": "GAME_ERROR", "message": "没有活跃对话"})
            return

        dialogue = self._active_dialogues[npc_id]
        request_id = str(dialogue.get("request_id") or "")
        dialogue["messages"].append({"role": "user", "content": choice_text})
        if self.conversation_memory:
            self.conversation_memory.append_turn(request_id, ConversationTurn("player", choice_text))
            turn_context = self.conversation_memory.prepare_turn_context(ConversationTurnRequest(
                conversation_id=request_id,
                speaker_id=npc_id,
                listener_ids=[str(dialogue.get("target") or "player")],
                utterance=choice_text,
                location_id=str(dialogue.get("location") or ""),
                game_time=str(dialogue.get("game_time") or ""),
                mode="player_dialogue",
            ))
            await self._send_retrieval_diagnostic(ws, request_id, npc_id)
            refreshed_system = self.prompt_builder.build(
                npc_id,
                str(dialogue.get("target") or "player"),
                game_time=str(dialogue.get("game_time") or ""),
                location=str(dialogue.get("location") or ""),
                turn_context=turn_context,
            )
            dialogue["messages"] = refreshed_system + [
                message for message in dialogue["messages"] if message.get("role") != "system"
            ]

        started = time.perf_counter()
        full_text = ""
        try:
            stream = llm_module.llm_client.chat_stream(
                dialogue["messages"],
                temperature=0.85,
            )
            for token in stream:
                full_text += token
                await ws.send_json({
                    "type": "DIALOGUE_TOKEN",
                    "npc_id": npc_id,
                    "token": token,
                    "is_complete": False,
                })
        except Exception as e:
            logger.error(f"LLM 错误: {e}")
            self._active_dialogues.pop(npc_id, None)
            if self.conversation_memory:
                self.conversation_memory.release(request_id)
            await ws.send_json({
                "type": "DIALOGUE_CLOSE",
                "npc_id": npc_id,
                "reason": "llm_error",
            })
            return

        dialogue["messages"].append({"role": "assistant", "content": full_text})
        if self.conversation_memory:
            self.conversation_memory.append_turn(request_id, ConversationTurn(npc_id, full_text))
        logger.info(
            "[PERF] player_dialogue_reply npc=%s elapsed=%.2fs chars=%s",
            npc_id,
            time.perf_counter() - started,
            len(full_text),
        )
        await ws.send_json({
            "type": "DIALOGUE_COMPLETE",
            "npc_id": npc_id,
            "npc_text_complete": full_text,
            "choices": [],
        })
        self._schedule_player_reply_choices(ws, npc_id, dialogue, full_text)

    async def _send_retrieval_diagnostic(self, ws: Any, conversation_id: str, speaker_id: str) -> None:
        """把本轮结构化检索快照发送给 Unity 诊断缓存。"""
        if not self.conversation_memory:
            return
        payload = self.conversation_memory.get_diagnostic(conversation_id, speaker_id)
        if payload:
            await ws.send_json({"type": "DIALOGUE_RETRIEVAL_DIAGNOSTIC", **payload})

    async def end_dialogue(self, ws: Any, msg: dict) -> None:
        """对话结束，记录短期记忆并提取玩家记忆。"""
        npc_id = msg.get("npc_id", "")
        reason = msg.get("reason", "player_left")
        request_id = str(msg.get("request_id") or "")

        if request_id:
            self._prepared_dialogues.pop(request_id, None)
        else:
            stale_ids = [
                prepared_id
                for prepared_id, prepared in self._prepared_dialogues.items()
                if prepared.get("npc_id") == npc_id
            ]
            for prepared_id in stale_ids:
                self._prepared_dialogues.pop(prepared_id, None)

        dialogue = self._active_dialogues.pop(npc_id, None)
        if not dialogue:
            return

        conversation_id = str(dialogue.get("request_id") or request_id)

        # 首轮内容尚未生成时只关闭会话，不把准备提示误写成真实互动记忆。
        if not any(message.get("role") == "assistant" for message in dialogue.get("messages", [])):
            if self.conversation_memory:
                self.conversation_memory.release(conversation_id)
            await ws.send_json({"type": "DIALOGUE_CLOSE", "npc_id": npc_id, "reason": reason})
            return

        if reason not in {"player_left", "completed", "normal"}:
            if self.conversation_memory:
                self.conversation_memory.release(conversation_id)
            await ws.send_json({"type": "DIALOGUE_CLOSE", "npc_id": npc_id, "reason": reason})
            return

        logger.info(f"对话结束: {npc_id} ({reason})")
        started = time.perf_counter()
        summaries = await self._summarize_dialogue_once(dialogue, npc_id)
        event_text = summaries["npc_memory"]
        logger.info(
            "[PERF] dialogue_end_summary npc=%s elapsed=%.2fs npc_chars=%s player_chars=%s",
            npc_id,
            time.perf_counter() - started,
            len(summaries["npc_memory"]),
            len(summaries["player_memory"]),
        )

        self.sqlite.execute(
            """INSERT INTO short_term_memories
               (id, subject_id, type, content, importance, emotional_valence,
                location, participants, created_at_game_time)
               VALUES (?, ?, 'interaction', ?, 0.5, 0.0, NULL, ?, ?)""",
            (
                f"stm_{uuid.uuid4().hex[:8]}",
                npc_id,
                event_text,
                json.dumps([dialogue["target"], npc_id]),
                str(dialogue.get("game_time") or ""),
            ),
        )

        if self.vector_store:
            await self._write_player_memory(dialogue, npc_id, summaries["player_memory"])

        self.sqlite.execute(
            "UPDATE npc_states SET is_first_encounter = 0 WHERE npc_id = ? AND is_first_encounter = 1",
            (npc_id,),
        )
        base_world_revision = int(msg.get("world_revision") or 0)
        state_effect = None
        if self.state_mgr and dialogue["messages"]:
            state_effect = self.state_mgr.apply_interaction_effect(
                npc_id,
                dialogue["target"],
                event_text[:180],
                source="player_dialogue",
                base_world_revision=base_world_revision,
                operation_id=f"{conversation_id}:state:{npc_id}",
            )
            if state_effect:
                await ws.send_json(state_effect)

        if self.conversation_memory:
            self.conversation_memory.release(conversation_id)

        if self.schedule_replan_context_sender is not None:
            await self.schedule_replan_context_sender({
                "operation_id": conversation_id,
                "npc_ids": [npc_id],
                "participant_ids": [dialogue["target"], npc_id],
                "interaction_type": "player_dialogue",
                "end_reason": reason,
                "interaction_summary": event_text,
                "location_id": str(dialogue.get("location") or ""),
                "state_effects": [state_effect] if state_effect else [],
                "base_world_revision": base_world_revision,
            })

        await ws.send_json({"type": "DIALOGUE_CLOSE", "npc_id": npc_id, "reason": reason})

    async def _summarize_dialogue_once(self, dialogue: dict, npc_id: str) -> dict[str, str]:
        """一次 LLM 请求同时生成 NPC 短期记忆和玩家向量记忆摘要。"""
        npc_name = (
            self.prompt_builder._get_target_name(npc_id)
            if hasattr(self.prompt_builder, "_get_target_name")
            else npc_id
        )
        dialogue_lines: list[str] = []
        for message in dialogue["messages"]:
            if message["role"] == "user":
                dialogue_lines.append(f"玩家: {message['content'][:200]}")
            elif message["role"] == "assistant":
                dialogue_lines.append(f"{npc_name}: {message['content'][:200]}")

        fallback_npc = "对话记录: " + " | ".join(line[:100] for line in dialogue_lines[-8:])[:240]
        fallback_player = " | ".join(line[:80] for line in dialogue_lines[-6:])[:200]

        try:
            summary_prompt = [
                {
                    "role": "system",
                    "content": (
                        "你负责把一段玩家与 NPC 的对话同时整理成两种记忆。"
                        "只输出 JSON，格式为 "
                        '{"npc_memory":"NPC第一人称日记，1-3句话",'
                        '"player_memory":"玩家视角值得记住的事，1-2句话"}'
                    ),
                },
                {"role": "user", "content": "对话:\n" + "\n".join(dialogue_lines)},
            ]
            raw = await llm_module.llm_client.chat_async(summary_prompt, temperature=0.55)
            data = json.loads(raw.strip().lstrip("```json").rstrip("```").strip())
            npc_memory = str(data.get("npc_memory", "")).strip() or fallback_npc
            player_memory = str(data.get("player_memory", "")).strip() or fallback_player
        except Exception:
            npc_memory = fallback_npc
            player_memory = fallback_player

        return {
            "npc_memory": npc_memory[:320],
            "player_memory": player_memory[:240],
        }

    async def _write_player_memory(self, dialogue: dict, npc_id: str, summary: str) -> None:
        """把已生成的玩家摘要写入玩家向量记忆。"""
        npc_name = (
            self.prompt_builder._get_target_name(npc_id)
            if hasattr(self.prompt_builder, "_get_target_name")
            else npc_id
        )

        dialogue_lines: list[str] = []
        for message in dialogue["messages"]:
            if message["role"] == "user":
                dialogue_lines.append(f"玩家: {message['content'][:200]}")
            elif message["role"] == "assistant":
                dialogue_lines.append(f"{npc_name}: {message['content'][:200]}")

        value = f"[{npc_name}] {summary}\n---\n" + "\n".join(dialogue_lines[-6:])

        try:
            vecs = encode_batch([summary])
            if vecs is not None:
                self.vector_store.upsert_node(
                    "player",
                    {
                        "node_id": f"pmem_{uuid.uuid4().hex[:8]}",
                        "vector": vecs[0].tolist(),
                        "type": "player_memory",
                        "value": value,
                        "importance": 0.5,
                        "created_day": int(dialogue.get("game_day") or 1),
                        "archived": 0,
                    },
                )
                logger.info("[MEMORY] player_memory_write npc=%s success=1 chars=%s", npc_id, len(summary))
        except Exception as e:
            logger.warning(f"玩家记忆写入失败: {e}")
            logger.info("[MEMORY] player_memory_write npc=%s success=0 error=%s", npc_id, e)

    def _schedule_player_reply_choices(self, ws: Any, npc_id: str, dialogue: dict, npc_reply: str) -> None:
        """后台生成玩家建议回复，避免阻塞 NPC 回复完成。"""
        snapshot = {
            "messages": list(dialogue.get("messages", [])),
            "target": dialogue.get("target", "player"),
            "location": dialogue.get("location", ""),
        }
        asyncio.create_task(self._send_player_reply_choices_update(ws, npc_id, snapshot, npc_reply))

    async def _send_player_reply_choices_update(self, ws: Any, npc_id: str, dialogue: dict, npc_reply: str) -> None:
        """生成真实建议并通过 WS 更新前端选项。"""
        started = time.perf_counter()
        choices = await self._build_player_reply_choices(npc_id, dialogue, npc_reply)
        elapsed = time.perf_counter() - started
        logger.info(
            "[PERF] player_reply_choices npc=%s elapsed=%.2fs choices=%s",
            npc_id,
            elapsed,
            len(choices),
        )
        try:
            await ws.send_json({
                "type": "DIALOGUE_CHOICES_UPDATE",
                "npc_id": npc_id,
                "choices": choices,
            })
        except Exception as e:
            logger.debug(f"玩家建议回复推送失败 ({npc_id}): {e}")

    def search_player_memories(self, about_npc: str, limit: int = 5) -> list[str]:
        """搜索玩家关于某 NPC 的记忆。"""
        if not self.vector_store:
            return []
        try:
            vecs = encode_batch([f"关于{about_npc}的回忆"])
            if vecs is None:
                return []
            results = self.vector_store.search("player", vecs[0].tolist(), top_k=limit)
            return [result.get("value", "") for result in results if result.get("value")]
        except Exception as e:
            logger.warning(f"玩家记忆搜索失败: {e}")
            return []

    async def _build_player_reply_choices(self, npc_id: str, dialogue: dict, npc_reply: str) -> list[str]:
        """为当前这轮 NPC 回复生成 3 条玩家可点击建议。"""
        started = time.perf_counter()
        target_id = dialogue.get("target", "player")
        location = dialogue.get("location", "")
        messages = dialogue.get("messages", [])
        player_memories: list[str] = []
        npc_name = npc_id
        choices: list[str] = []
        rejected_choices: list[dict[str, str]] = []
        fallback_used = False
        failure_reason = ""

        try:
            player_memories = self._get_player_reply_memories(npc_id, target_id)
            npc_name = str(self.prompt_builder._load_profile(npc_id).get("name", npc_id))
            prompt_messages = self.prompt_builder.build_player_reply_suggestions(
                npc_id,
                target_id=target_id,
                npc_reply=npc_reply,
                dialogue_messages=messages,
                player_memories=player_memories,
                game_time=str(dialogue.get("game_time") or ""),
                location=location,
            )
            raw = await llm_module.llm_client.chat_async(
                prompt_messages,
                temperature=0.7,
            )
            parsed, rejected_choices = self._parse_player_reply_choices(
                raw,
                npc_name,
                include_rejections=True,
            )
            if len(parsed) >= 3:
                choices = parsed[:3]
            else:
                choices = self._merge_with_fallback_choices(parsed, npc_reply)
                fallback_used = True
        except Exception as e:
            logger.warning(f"玩家建议回复生成失败 ({npc_id}): {e}")
            failure_reason = f"generation_failed:{type(e).__name__}"
            fallback_used = True
            choices = self._fallback_player_reply_choices(npc_reply)

        self.reply_suggestion_traces.record(
            npc_id=npc_id,
            player_id=target_id,
            context_keys=PLAYER_REPLY_SUGGESTION_CONTEXT_KEYS,
            choices=choices,
            rejected_choices=rejected_choices,
            fallback_used=fallback_used,
            failure_reason=failure_reason,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )
        return choices

    def _parse_player_reply_choices(self, raw_text: str, npc_name: str = "", include_rejections: bool = False):
        """解析 LLM 返回的建议回复，尽量稳定收敛到 3 条字符串。"""
        if not raw_text:
            return ([], []) if include_rejections else []

        candidates: list[str] = []
        cleaned = raw_text.strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                values = data.get("choices", [])
                if isinstance(values, list):
                    candidates.extend(str(item) for item in values)
            elif isinstance(data, list):
                candidates.extend(str(item) for item in data)
        except Exception:
            pass

        if not candidates:
            lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
            for line in lines:
                normalized = re.sub(r"^[\-\*\d\.\)\(、\s]+", "", line).strip()
                if normalized:
                    candidates.append(normalized)

        deduped: list[str] = []
        seen: set[str] = set()
        rejected_choices: list[dict[str, str]] = []
        for item in candidates:
            normalized = str(item).strip().strip("\"'“”")
            normalized = re.sub(r"\s+", " ", normalized)
            if not normalized:
                continue
            if len(normalized) > 30:
                normalized = normalized[:30].rstrip("，。！？、,.!? ")
            if not normalized or normalized in seen:
                continue
            if not self._is_player_reply_choice_safe(normalized, npc_name):
                rejected_choices.append({
                    "choice": normalized,
                    "reason": self._player_reply_choice_rejection_reason(normalized, npc_name) or "invalid_choice",
                })
                continue
            seen.add(normalized)
            deduped.append(normalized)
            if len(deduped) >= 3:
                break

        if include_rejections:
            return deduped, rejected_choices
        return deduped

    @staticmethod
    def _is_player_reply_choice_safe(choice: str, npc_name: str) -> bool:
        """只接受不含确定性 NPC 冒充或开头舞台动作的玩家台词。"""
        return PlayerDialogueService._player_reply_choice_rejection_reason(choice, npc_name) is None

    @staticmethod
    def _player_reply_choice_rejection_reason(choice: str, npc_name: str) -> str | None:
        """返回确定性主体违规原因，避免在解析器中扩张自然语言语义规则。"""
        normalized = str(choice or "").strip()
        if npc_name and re.match(rf"^{re.escape(npc_name)}\s*[:：]", normalized):
            return "npc_name_prefix"
        if re.match(r"^(?:（[^）]*）|\([^)]*\))", normalized):
            return "leading_stage_direction"
        return None

    def _fallback_player_reply_choices(self, npc_reply: str) -> list[str]:
        """LLM 失败时返回 3 条稳妥的默认建议，不影响自由输入继续使用。"""
        snippet = (npc_reply or "").strip()
        if len(snippet) > 18:
            snippet = snippet[:18].rstrip("，。！？、,.!? ")

        base_choices = [
            "嗯，我明白你的意思。",
            "那后来怎么样了？",
            "听起来还挺有意思的。",
        ]

        if snippet:
            contextual = f"你刚才说的“{snippet}”是怎么回事？"
            contextual = contextual[:30].rstrip("，。！？、,.!? ")
            base_choices[1] = contextual or base_choices[1]

        return base_choices[:3]

    def _format_visual_context(self, raw_context: Any) -> str:
        """把前端空闲表现快照格式化为当前对话开场提示。"""
        if not isinstance(raw_context, dict):
            return ""

        ambient_action = str(raw_context.get("ambient_action_id") or "").strip()
        ambient_label = str(raw_context.get("ambient_label") or "").strip()
        if not ambient_action and not ambient_label:
            return ""

        base_action = str(raw_context.get("base_action_id") or "stand").strip()[:40]
        location_id = str(raw_context.get("location_id") or "").strip()[:80]
        visible_action = (ambient_label or ambient_action)[:80]
        interrupted = bool(raw_context.get("is_interrupting_ambient"))
        interrupt_text = "玩家搭话时打断了这个小动作。" if interrupted else ""

        return (
            "临场视觉上下文：玩家刚才看到你"
            f"{visible_action}。地点={location_id or '未知'}，主行为={base_action or 'stand'}。"
            f"{interrupt_text}"
            "这是 Unity 前端空闲表现快照，只用于当前对话开场，不要当作长期日程或记忆事实。"
        )

    def _merge_with_fallback_choices(self, parsed_choices: list[str], npc_reply: str) -> list[str]:
        """当模型返回不足 3 条时，用兜底建议补满。"""
        merged: list[str] = []
        seen: set[str] = set()

        for item in parsed_choices + self._fallback_player_reply_choices(npc_reply):
            normalized = (item or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
            if len(merged) >= 3:
                break

        return merged[:3]

    def _get_player_reply_memories(self, npc_id: str, target_id: str) -> list[str]:
        """为玩家建议回复查询与当前 NPC 相关的玩家向量记忆。"""
        if target_id != "player":
            return []

        npc_name = self.prompt_builder._get_target_name(npc_id)
        memories = self.search_player_memories(npc_name, limit=3)
        if memories:
            return memories

        if npc_name != npc_id:
            return self.search_player_memories(npc_id, limit=3)

        return []

    def _dialogue_pause_reason(self, npc_id: str) -> str:
        """为玩家对话构造稳定的时钟暂停 key。"""
        return f"player_dialogue:{npc_id or 'unknown'}"
