"""后端运行时编排器。"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .. import config as cfg_module
from ..database.sqlite_client import SQLiteClient
from ..dialogue import llm_client as llm_module
from ..dialogue.conversation_memory import ConversationMemoryCoordinator
from ..dialogue.prompt_builder import PromptBuilder, _parse_day
from ..memory.evolution import EvolutionEngine
from ..memory.manager import MemoryManager
from ..memory.midnight_coordinator import MidnightCoordinator
from ..memory.player_events import PlayerEventMemoryWriter
from ..memory.retrieval import init_retrieval
from ..npc.behavior_engine import BehaviorEngine
from ..npc.npc_dialogue import NpcDialogueManager
from ..npc.player_impression_refresh import PlayerImpressionRefresher
from ..npc.state_manager import StateManager
from ..npc.social_session import NpcSocialContentService
from ..npc.social_decision import NpcSocialDecisionService, SocialDecisionRequest
from ..npc.schedule_world_snapshot import ScheduleWorldSnapshot, ScheduleWorldSnapshotStore
from ..protocol.codec import DecodedMessage
from ..protocol.session import ProtocolSession
from ..save.manager import SaveManager
from ..save.memory_checkpoint import MemoryCheckpointService
from .dialogue_service import PlayerDialogueService
from .message_bus import MessageBus
from .operation_context import GameTimeSnapshot
from .services import AppServices
from .world_preparation import WorldPreparationCoordinator, WorldPreparationSnapshot

logger = logging.getLogger("sakurabashi.runtime")


class GameRuntime:
    """统一管理后端服务生命周期与消息编排。"""

    def __init__(self):
        self.message_bus = MessageBus()
        self.services: AppServices | None = None
        self.dialogue_service: PlayerDialogueService | None = None
        self._background_tasks: set[asyncio.Task] = set()
        self.social_content: NpcSocialContentService | None = None
        self.world_preparation: WorldPreparationCoordinator | None = None
        self.midnight_coordinator: MidnightCoordinator | None = None
        self.social_decisions: NpcSocialDecisionService | None = None
        self.schedule_snapshots = ScheduleWorldSnapshotStore()

    def require_services(self) -> AppServices:
        if self.services is None:
            raise RuntimeError("runtime not started")
        return self.services

    def require_dialogue_service(self) -> PlayerDialogueService:
        if self.dialogue_service is None:
            raise RuntimeError("dialogue service not started")
        return self.dialogue_service

    def _get_vector_store(self, sqlite: SQLiteClient):
        """加载向量存储（LanceDB 优先，SQLite 兜底）。"""
        try:
            from ..database.lancedb_client import LanceDBClient

            return LanceDBClient(cfg_module.config.lancedb_path, cfg_module.config.npc_ids)
        except Exception as e:
            logger.warning(f"LanceDB 不可用({e})，降级 SQLite")
            from ..memory.vector_store import VectorStore

            return VectorStore(sqlite)

    async def start(self) -> None:
        """初始化后端全部服务。"""
        logger.info("=== 樱桥通后端启动 ===")

        cfg_module.init_config()
        logger.info(f"配置: {cfg_module.config.sqlite_path}")

        sqlite = SQLiteClient(cfg_module.config.sqlite_path)
        logger.info("SQLite 就绪 (8 张表)")

        vector_store = self._get_vector_store(sqlite)
        state_mgr = StateManager(sqlite, vector_store)
        prompt_builder = PromptBuilder(sqlite, str(cfg_module.CONFIG_DIR / "npc_profiles"))
        prompt_builder.set_state_manager(state_mgr)
        mem_mgr = MemoryManager(sqlite, vector_store)
        retrieval = init_retrieval(sqlite, vector_store, clarity_recover=mem_mgr.recover_clarity)
        state_mgr.set_retrieval(retrieval)
        prompt_builder.set_retrieval(retrieval)
        logger.info("图检索就绪")
        conversation_memory = ConversationMemoryCoordinator(sqlite, retrieval)

        evolution = EvolutionEngine(sqlite, vector_store)
        logger.info("演化引擎就绪")
        player_events = PlayerEventMemoryWriter(sqlite)

        save_mgr = SaveManager(sqlite, str(cfg_module.SAVE_DIR), str(cfg_module.DATA_DIR))
        memory_checkpoints = MemoryCheckpointService(
            cfg_module.config.sqlite_path,
            cfg_module.config.lancedb_path,
            str(cfg_module.SAVE_DIR / "MemoryCheckpoints"),
        )
        logger.info(f"存档就绪: {cfg_module.SAVE_DIR}")

        behavior = BehaviorEngine(
            sqlite,
            cfg_module.config.actions,
            cfg_module.config.locations,
        )
        behavior.set_state_manager(state_mgr)
        behavior.set_ws_sender(self.message_bus.broadcast)
        behavior.schedule_snapshot_store = self.schedule_snapshots
        self.social_decisions = NpcSocialDecisionService(
            lambda request: self._decide_social_semantics(behavior, request)
        )
        logger.info("行为引擎就绪")

        llm_module.init_llm(
            cfg_module.config.llm_provider,
            cfg_module.config.llm_model,
            cfg_module.config.llm_api_key,
            cfg_module.config.llm_base_url,
            cfg_module.config.llm_thinking_mode,
        )
        logger.info(f"LLM 就绪: {cfg_module.config.llm_provider}/{cfg_module.config.llm_model}")

        npc_dialogue = NpcDialogueManager(prompt_builder, self.message_bus.broadcast, sqlite, state_mgr)
        self.social_content = NpcSocialContentService(
            npc_dialogue,
            completion_callback=self._broadcast_schedule_replan_context,
        )
        prompt_builder.set_plan_provider(behavior.get_remaining_plan_summary)
        logger.info("NPC 对话管理器就绪")

        self.services = AppServices(
            sqlite=sqlite,
            vector_store=vector_store,
            state_mgr=state_mgr,
            prompt_builder=prompt_builder,
            mem_mgr=mem_mgr,
            retrieval=retrieval,
            evolution=evolution,
            save_mgr=save_mgr,
            memory_checkpoints=memory_checkpoints,
            behavior=behavior,
            npc_dialogue=npc_dialogue,
            player_events=player_events,
        )
        self.dialogue_service = PlayerDialogueService(
            prompt_builder,
            sqlite,
            vector_store,
            state_mgr,
            conversation_memory=conversation_memory,
            schedule_replan_context_sender=self._broadcast_schedule_replan_context,
        )
        self.world_preparation = WorldPreparationCoordinator(
            sqlite=sqlite,
            state_manager=state_mgr,
            behavior=behavior,
            run_midnight_maintenance=self._run_midnight_maintenance,
        )

        logger.info(f"REST http://{cfg_module.config.host}:{cfg_module.config.rest_port}")
        logger.info(f"WS   ws://{cfg_module.config.host}:{cfg_module.config.rest_port}/ws")

    async def stop(self) -> None:
        """停止后端运行时。"""
        for task in self._background_tasks:
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
        logger.info("=== 樱桥通后端关闭 ===")

    async def _run_midnight_maintenance(self, game_day: int):
        """执行不含协议终态的午夜记忆与天气维护阶段。"""
        self._rebuild_midnight_coordinator(game_day)
        result = await self.midnight_coordinator.run(game_day)
        logger.info(
            "[PERF] midnight_total elapsed=%.2fs status=%s operation_id=%s parallel_wall=%.2fs",
            result.total_elapsed_sec,
            result.status,
            result.operation_id,
            result.parallel_wall_sec,
        )
        logger.info("睡眠处理完成，等待 Unity 提交次日世界状态")
        return result

    def poll_messages(self) -> list[dict]:
        return self.message_bus.drain()

    async def handle_message(self, ws: Any, msg: dict) -> None:
        """统一消息路由。"""
        msg_type = msg.get("type", "")
        if msg_type in {"GAME_PAUSE_STATE", "GAME_TIME_SYNC", "FAST_FORWARD"}:
            await ws.send_json({
                "type": "GAME_ERROR",
                "message": "legacy_time_control_removed",
                "rejected_type": msg_type,
            })
            return
        if msg_type == "MIDNIGHT_SETTLEMENT_REQUEST":
            try:
                result = await self.require_world_preparation().prepare_next_day(
                    msg.get("game_time") or {},
                    lambda snapshot: self._send_world_preparation_progress(ws, snapshot),
                )
                await ws.send_json({
                    "type": "MIDNIGHT_SETTLEMENT_COMPLETE",
                    "weather": result.weather,
                    "operation_id": result.operation_id,
                    "maintenance_status": result.maintenance_status,
                    "failure_reasons": list(result.maintenance_failure_reasons),
                })
            except Exception as error:
                logger.exception("Unity 请求的午夜结算失败")
                snapshot = self.require_world_preparation().snapshot
                await ws.send_json({
                    "type": "MIDNIGHT_SETTLEMENT_FAILED",
                    "operation_id": snapshot.operation_id,
                    "reason": snapshot.failure_reason or "world_preparation_failed",
                })
            return
        if msg_type == "NPC_SOCIAL_DECISION_REQUEST":
            if self.social_decisions is None:
                raise RuntimeError("social decision service not started")
            result = await self.social_decisions.decide(msg)
            await ws.send_json(result)
            return
        if msg_type == "NPC_SOCIAL_CONTENT_REQUEST":
            result = await self._require_social_content().handle_content_request(msg)
            await ws.send_json(result)
            return

        if msg_type == "NPC_SCHEDULE_REPLAN_REQUEST":
            try:
                await ws.send_json(await self.require_services().behavior.replan_from_unity_request(msg, self.schedule_snapshots))
            except Exception as error:
                logger.warning("日程重规划被拒绝: %s", type(error).__name__)
                await ws.send_json({
                    "type": "GAME_ERROR",
                    "request_id": msg.get("operation_id", ""),
                    "message": f"schedule_replan_rejected:{type(error).__name__}",
                })
            return

        services = self.require_services()
        dialogue_service = self.require_dialogue_service()

        if msg_type == "PING":
            await ws.send_json({"type": "PONG"})
        elif msg_type == "GAME_START":
            await self._handle_game_start(ws, msg)
        elif msg_type == "PLAYER_MOVE":
            location = msg.get("location_id", "street.crossroad")
            services.sqlite.execute(
                "UPDATE game_state SET player_location = ?, updated_at = datetime('now') WHERE id = 1",
                (location,),
            )
        elif msg_type == "PLAYER_EVENT":
            frozen_time = GameTimeSnapshot.from_dict(msg.get("game_time") or {})
            result = services.player_events.record_event(msg, frozen_time.time_label())
            await ws.send_json({"type": "PLAYER_EVENT_RECORDED", **result})
        elif msg_type == "NPC_RUNTIME_EVENT":
            result = services.behavior.handle_runtime_event(msg)
            await ws.send_json({
                "type": "NPC_RUNTIME_EVENT_ACK",
                "event_id": msg.get("event_id", ""),
                **result,
            })
        elif msg_type == "NPC_SOCIAL_FAILED":
            result = self._require_social_content().discard(msg)
            await ws.send_json({"type": "NPC_SOCIAL_ACK", "request_id": msg.get("request_id", ""), **result})
        elif msg_type == "NPC_SOCIAL_COMPLETE":
            result = await self._require_social_content().handle_complete(msg)
            await ws.send_json({"type": "NPC_SOCIAL_ACK", "request_id": msg.get("request_id", ""), **result})
        elif msg_type == "DIALOGUE_START":
            await dialogue_service.prepare_dialogue(ws, msg)
        elif msg_type == "DIALOGUE_READY":
            self._start_background_task(dialogue_service.start_ready_dialogue(ws, msg))
        elif msg_type == "PLAYER_CHOICE":
            await dialogue_service.handle_player_choice(ws, msg)
        elif msg_type == "DIALOGUE_END":
            await dialogue_service.end_dialogue(ws, msg)
        else:
            await ws.send_json({"type": "GAME_ERROR", "message": f"未实现: {msg_type}"})

    def _require_social_content(self) -> NpcSocialContentService:
        """返回不持有 Unity 运行时状态的 NPC 社交内容服务。"""
        if self.social_content is None:
            raise RuntimeError("NPC social content service not started")
        return self.social_content

    async def _broadcast_schedule_replan_context(self, context: dict) -> None:
        """向 Unity 广播互动后重规划上下文，由 Unity 回传权威剩余日程。"""
        await self.message_bus.broadcast({
            "type": "NPC_SCHEDULE_REPLAN_CONTEXT",
            "operation_id": str(context.get("operation_id") or ""),
            "interaction_id": str(context.get("operation_id") or ""),
            "npc_ids": list(context.get("npc_ids") or []),
            "participant_ids": list(context.get("participant_ids") or []),
            "interaction_type": str(context.get("interaction_type") or ""),
            "end_reason": str(context.get("end_reason") or ""),
            "interaction_summary": str(context.get("interaction_summary") or ""),
            "location_id": str(context.get("location_id") or ""),
            "game_time": context.get("game_time") or {},
            "state_effects": list(context.get("state_effects") or []),
            "base_world_revision": int(context.get("base_world_revision") or 0),
        })

    async def _decide_social_semantics(
        self,
        behavior: BehaviorEngine,
        request: SocialDecisionRequest,
    ) -> tuple[bool, str, str]:
        """复用现有关系/记忆 Prompt，只返回语义意愿。"""
        want = await behavior._llm_decide_talk(
            request.npc_id,
            request.target_npc_id,
            request.location_id,
        )
        return want, "semantic_interest" if want else "semantic_decline", ""

    async def handle_protocol_message(
        self,
        ws: Any,
        decoded: DecodedMessage,
        session: ProtocolSession,
    ) -> None:
        """处理 envelope 专属控制消息，并把兼容业务消息交给原路由。"""
        msg = decoded.message
        if msg.get("type") == "hello":
            dialogue_service = self.require_dialogue_service()
            dialogue_service.reset_transient_state()
            if self.social_content is not None:
                self.social_content.reset()
            session.is_negotiated = True
            await ws.send_json(session.response(
                "hello_ack",
                {
                    "accepted_protocol_version": 1,
                    "server_role": "memory_backend",
                    "capabilities": ["memory_checkpoint", "world_snapshot", "request_deduplication"],
                },
                decoded.request_id,
            ))
            return
        if msg.get("type") == "world_snapshot":
            try:
                self._apply_world_snapshot(msg)
                schedule_payload = msg.get("npc_schedule_physical_state")
                if schedule_payload is not None:
                    self.schedule_snapshots.put(ScheduleWorldSnapshot.from_dict(schedule_payload))
                await ws.send_json(session.response(
                    "world_snapshot_applied",
                    {"world_revision": int(msg.get("world_revision") or 0)},
                    decoded.request_id,
                ))
            except Exception as error:
                await ws.send_json(session.response(
                    "world_snapshot_failed",
                    {"reason": str(error)},
                    decoded.request_id,
                ))
            return
        if msg.get("type") == "memory_checkpoint_prepare":
            try:
                manifest = self.require_services().memory_checkpoints.prepare(
                    str(msg.get("slot_id") or ""),
                    str(msg.get("checkpoint_id") or ""),
                )
                await ws.send_json(session.response(
                    "memory_checkpoint_prepared",
                    {"manifest": manifest},
                    decoded.request_id,
                ))
            except Exception as error:
                await ws.send_json(session.response(
                    "memory_checkpoint_prepare_failed",
                    {"reason": str(error)},
                    decoded.request_id,
                ))
            return
        if msg.get("type") == "memory_checkpoint_commit":
            try:
                manifest = self.require_services().memory_checkpoints.commit(
                    str(msg.get("slot_id") or ""),
                    str(msg.get("checkpoint_id") or ""),
                )
                await ws.send_json(session.response(
                    "memory_checkpoint_committed",
                    {"manifest": manifest},
                    decoded.request_id,
                ))
            except Exception as error:
                await ws.send_json(session.response(
                    "memory_checkpoint_commit_failed",
                    {"reason": str(error)},
                    decoded.request_id,
                ))
            return
        if msg.get("type") == "memory_checkpoint_abort":
            self.require_services().memory_checkpoints.abort(
                str(msg.get("slot_id") or ""),
                str(msg.get("checkpoint_id") or ""),
            )
            await ws.send_json(session.response("memory_checkpoint_aborted", {}, decoded.request_id))
            return
        if msg.get("type") == "memory_checkpoint_finalize":
            try:
                manifest = self.require_services().memory_checkpoints.finalize(
                    str(msg.get("slot_id") or ""),
                    str(msg.get("checkpoint_id") or ""),
                )
                await ws.send_json(session.response(
                    "memory_checkpoint_finalized",
                    {"manifest": manifest},
                    decoded.request_id,
                ))
            except Exception as error:
                await ws.send_json(session.response(
                    "memory_checkpoint_finalize_failed",
                    {"reason": str(error)},
                    decoded.request_id,
                ))
            return
        if msg.get("type") == "memory_checkpoint_load":
            try:
                manifest = self.require_services().memory_checkpoints.load(
                    str(msg.get("slot_id") or ""),
                    str(msg.get("checkpoint_id") or ""),
                )
                self._refresh_vector_services()
                await ws.send_json(session.response(
                    "memory_checkpoint_loaded",
                    {"manifest": manifest},
                    decoded.request_id,
                ))
            except Exception as error:
                await ws.send_json(session.response(
                    "memory_checkpoint_load_failed",
                    {"reason": str(error)},
                    decoded.request_id,
                ))
            return
        if msg.get("type") == "memory_checkpoint_delete":
            try:
                self.require_services().memory_checkpoints.delete(
                    str(msg.get("slot_id") or ""),
                    str(msg.get("checkpoint_id") or ""),
                )
                await ws.send_json(session.response(
                    "memory_checkpoint_deleted",
                    {},
                    decoded.request_id,
                ))
            except Exception as error:
                await ws.send_json(session.response(
                    "memory_checkpoint_delete_failed",
                    {"reason": str(error)},
                    decoded.request_id,
                ))
            return
        if msg.get("type") == "memory_checkpoints_purge_all":
            try:
                self.require_services().memory_checkpoints.purge_all()
                await ws.send_json(session.response(
                    "memory_checkpoints_purged_all",
                    {},
                    decoded.request_id,
                ))
            except Exception as error:
                await ws.send_json(session.response(
                    "memory_checkpoints_purge_all_failed",
                    {"reason": str(error)},
                    decoded.request_id,
                ))
            return
        await self.handle_message(ws, msg)

    def _apply_world_snapshot(self, msg: dict) -> None:
        """用 Unity 权威世界快照覆盖 Python 推理缓存。"""
        services = self.require_services()
        game_time = msg.get("game_time") or {}
        player = msg.get("player") or {}
        services.sqlite.execute(
            """UPDATE game_state SET game_day=?, game_hour=?, game_minute=?, weather=?,
               player_location=?, updated_at=datetime('now') WHERE id=1""",
            (
                int(game_time.get("day") or 1),
                int(game_time.get("hour") or 0),
                int(game_time.get("minute") or 0),
                str(msg.get("weather") or game_time.get("weather") or "sunny"),
                str(player.get("location_id") or "player_cafe.doorway"),
            ),
        )
        for npc in msg.get("npcs") or []:
            services.sqlite.execute(
                """UPDATE npc_states SET current_location=?, emotion=?, energy=?, sociability=?,
                   is_asleep=?, movement_origin='', movement_target='', movement_status='',
                   current_action=NULL, updated_at=datetime('now') WHERE npc_id=?""",
                (
                    str(npc.get("location_id") or ""),
                    str(npc.get("emotion") or "平静"),
                    float(npc.get("energy") or 0.0),
                    float(npc.get("sociability") or 0.0),
                    1 if npc.get("is_asleep") else 0,
                    str(npc.get("npc_id") or ""),
                ),
            )

    def _start_background_task(self, coroutine) -> None:
        """托管耗时协议任务，避免阻塞 WebSocket 的下一次 receive。"""
        task = asyncio.create_task(coroutine)
        self._background_tasks.add(task)
        task.add_done_callback(self._on_background_task_done)

    def _on_background_task_done(self, task: asyncio.Task) -> None:
        """清理后台任务并记录未在业务层收口的异常。"""
        self._background_tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error(
                "后台协议任务失败",
                exc_info=(type(error), error, error.__traceback__),
            )

    async def _handle_game_start(self, ws: Any, msg: dict) -> None:
        """冷启动或续玩，并启动时钟。"""
        mode = msg.get("mode", "CONTINUE")
        try:
            result = await self.require_world_preparation().prepare_initial_world(
                mode,
                msg.get("game_time") or {},
                lambda snapshot: self._send_world_preparation_progress(ws, snapshot),
            )
        except Exception:
            snapshot = self.require_world_preparation().snapshot
            await ws.send_json({
                "type": "GAME_ERROR",
                "request_id": snapshot.operation_id,
                "message": snapshot.failure_reason or "world_preparation_failed",
            })
            return
        await ws.send_json(
            {
                "type": "GAME_READY",
                "mode": mode,
                "fresh_start": (mode == "NEW_GAME"),
                "game_time": {
                    "day": result.game_time.day,
                    "hour": result.game_time.hour,
                    "minute": result.game_time.minute,
                    "weather": result.game_time.weather,
                    "time_revision": result.game_time.time_revision,
                },
                "weather": result.weather,
                "player_location": "player_cafe.doorway",
                "npcs": result.npcs,
                "operation_id": result.operation_id,
            }
        )
        logger.info("GAME_READY: %s NPCs, %s", len(result.npcs), result.game_time.time_label())

    def require_world_preparation(self) -> WorldPreparationCoordinator:
        """返回已装配的世界准备协调器。"""
        if self.world_preparation is None:
            raise RuntimeError("world preparation is not started")
        return self.world_preparation

    async def _send_world_preparation_progress(self, ws: Any, snapshot: WorldPreparationSnapshot) -> None:
        """向当前请求方发送稳定的阶段进度协议包。"""
        messages = {
            "initial_memory": "正在整理初始记忆…",
            "memory_settlement": "正在沉淀今日见闻…",
            "daily_plans": "正在为居民安排今日行程…",
            "entering_world": "正在进入街区…",
        }
        await ws.send_json({
            "type": "WORLD_PREPARATION_PROGRESS",
            "operation_id": snapshot.operation_id,
            "flow": snapshot.flow,
            "phase": snapshot.phase,
            "message": messages.get(snapshot.phase, "正在准备世界…"),
            "progress_floor": snapshot.progress_floor,
            "target_game_day": snapshot.target_game_day,
        })

    def _refresh_vector_services(self) -> None:
        """在存档恢复后重建向量层相关服务，确保句柄与数据一致。"""
        services = self.require_services()
        vector_store = self._get_vector_store(services.sqlite)
        services.vector_store = vector_store
        services.state_mgr = StateManager(services.sqlite, vector_store)
        services.prompt_builder.set_state_manager(services.state_mgr)
        services.mem_mgr = MemoryManager(services.sqlite, vector_store)
        services.retrieval = init_retrieval(
            services.sqlite,
            vector_store,
            clarity_recover=services.mem_mgr.recover_clarity,
        )
        services.state_mgr.set_retrieval(services.retrieval)
        services.prompt_builder.set_retrieval(services.retrieval)
        services.evolution = EvolutionEngine(services.sqlite, vector_store)
        services.player_events = PlayerEventMemoryWriter(services.sqlite)
        services.behavior.set_state_manager(services.state_mgr)
        if self.dialogue_service:
            self.dialogue_service.vector_store = vector_store
            self.dialogue_service.state_mgr = services.state_mgr
        if services.npc_dialogue:
            services.npc_dialogue._state_mgr = services.state_mgr
        self.midnight_coordinator = None

    def _rebuild_midnight_coordinator(self, game_day: int) -> None:
        """按当前服务句柄重建午夜深模块，供启动和存档恢复共用。"""
        services = self.require_services()
        refresher = PlayerImpressionRefresher(
            services.state_mgr,
            services.retrieval,
            cfg_module.config.npc_ids,
        )
        self.midnight_coordinator = MidnightCoordinator(
            refresher,
            self._run_edge_decay,
            lambda: self._run_extraction(game_day),
            lambda: self._run_graph_evolution(game_day),
            lambda: self._run_short_term_migration(game_day),
        )

    def _run_edge_decay(self) -> None:
        services = self.require_services()
        total_decayed = 0
        total_deleted = 0
        total_orphans = 0
        for npc_id in cfg_module.config.npc_ids:
            d, deleted = services.mem_mgr.clarity_decay_edges(npc_id)
            total_decayed += d
            total_deleted += deleted
            total_orphans += services.mem_mgr.cleanup_orphan_nodes(npc_id)
        logger.info(
            f"午夜衰减: {total_decayed} 边衰减, {total_deleted} 边删除, {total_orphans} 孤点归档"
        )

    async def _run_extraction(self, game_day: int) -> dict:
        """并发提取各 NPC 当日事件并返回结构化局部失败统计。"""
        started = time.perf_counter()
        services = self.require_services()

        async def extract_one(npc_id: str) -> dict:
            """提取单个 NPC 的当日事件。"""
            events = services.sqlite.fetchall(
                "SELECT content FROM short_term_memories WHERE subject_id = ? "
                "AND created_at_game_time LIKE ?",
                (npc_id, f"第{game_day}天%"),
            )
            if not events:
                return {"owner_id": npc_id, "had_events": False, "success": True, "written_nodes": 0, "invalid_nodes": 0, "invalid_edges": 0}
            npc_name = (
                services.prompt_builder._get_target_name(npc_id)
                if hasattr(services.prompt_builder, "_get_target_name")
                else npc_id
            )
            combined = "\n---\n".join(event["content"] for event in events)
            extraction = await asyncio.to_thread(
                services.mem_mgr.extract_and_ingest,
                npc_id,
                npc_name,
                combined,
                f"第{game_day}天 23:59",
                game_day,
            )
            return {"owner_id": npc_id, "had_events": True, **extraction}

        tasks = [extract_one(nid) for nid in cfg_module.config.npc_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        summary = {
            "event_owner_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "invalid_node_count": 0,
            "invalid_edge_count": 0,
            "failed_owner_ids": [],
        }
        total_nodes = 0
        for index, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"提取失败 ({cfg_module.config.npc_ids[index]}): {result}")
                summary["failure_count"] += 1
                summary["failed_owner_ids"].append(cfg_module.config.npc_ids[index])
                continue
            if not result.get("had_events"):
                continue
            summary["event_owner_count"] += 1
            summary["invalid_node_count"] += int(result.get("invalid_nodes", 0))
            summary["invalid_edge_count"] += int(result.get("invalid_edges", 0))
            total_nodes += int(result.get("written_nodes", 0))
            if result.get("success"):
                summary["success_count"] += 1
            else:
                summary["failure_count"] += 1
                summary["failed_owner_ids"].append(result["owner_id"])
        if total_nodes:
            logger.info(f"事件→图提取: {total_nodes} nodes created")
        summary["elapsed_sec"] = time.perf_counter() - started
        return summary

    async def _run_graph_evolution(self, game_day: int) -> None:
        """等待事件提取完成后执行当晚图演化。"""
        await asyncio.to_thread(
            self.require_services().evolution.run_all_sync,
            cfg_module.config.npc_ids,
            f"第{game_day}天 23:59",
        )

    def _run_short_term_migration(self, game_day: int) -> None:
        services = self.require_services()
        cutoff_day = game_day - cfg_module.config.short_term_days
        all_memories = services.sqlite.fetchall("SELECT id, created_at_game_time FROM short_term_memories")
        old = [m for m in all_memories if _parse_day(m["created_at_game_time"]) <= cutoff_day]
        if old:
            for row in old:
                services.sqlite.execute("DELETE FROM short_term_memories WHERE id = ?", (row["id"],))
            logger.info(
                f"短期记忆清理: {len(old)} 条过期删除 (>={cfg_module.config.short_term_days}天)"
            )
        else:
            logger.debug("短期记忆清理: 无需清理")

    @staticmethod
    def _random_weather() -> str:
        import random

        return random.choice(["sunny", "sunny", "sunny", "cloudy", "rainy"])
