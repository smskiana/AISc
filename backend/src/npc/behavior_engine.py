"""
NPC 行为语义引擎。

Unity 是 NPC 位置、P0/need/运行时状态、物理社交候选和任务终态的权威。
本模块只保留日程生成/互动后重规划 facade、社交语义意愿和少量对话上下文读取。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from pathlib import Path

from ..database.sqlite_client import SQLiteClient
from ..dialogue.player_name import get_player_display_name, load_player_profile, render_player_tokens
from ..prompting import PromptAssembler
from ..prompting.tag_formatter import format_npc
from ..application.operation_context import BrainOperationContext, GameTimeSnapshot
from .daily_schedule import (
    DailyScheduleBatchRequest,
    DailyScheduleItem,
    DailySchedulePlanner,
    InteractionReplanRequest,
    NpcScheduleRequest,
)
from .task_catalog import NpcTaskCatalog

logger = logging.getLogger("sakurabashi.behavior")

# ── 默认 routine（profile JSON 中没有 daily_rhythm 时的回退） ──
DEFAULT_ROUTINES: dict[str, list[tuple[int, int, str, str]]] = {
    "sakura": [
        (5, 30, "stand", "flower_shop.counter"),
        (8, 0, "work_open", "flower_shop.doorway"),
        (12, 0, "eat", "flower_shop.back_room"),
        (14, 0, "rest", "flower_shop.window_seat"),
        (18, 30, "work_close", "flower_shop.doorway"),
        (22, 30, "sleep", "flower_shop.back_room"),
    ],
    "chihaya": [
        (6, 0, "stand", "bakery.kneading_table"),
        (9, 0, "work_open", "bakery.doorway"),
        (12, 30, "eat", "bakery.counter"),
        (17, 30, "visit", "flower_shop.doorway"),
        (18, 0, "give_item", "flower_shop.counter"),
        (20, 30, "work_close", "bakery.doorway"),
    ],
    "kazuha": [
        (9, 0, "work_open", "bookstore.doorway"),
        (12, 0, "eat", "bookstore.reading_sofa"),
        (20, 0, "work_close", "bookstore.doorway"),
        (1, 0, "drink", "street.vending_machine"),
    ],
    "tatsunosuke": [
        (8, 0, "stand", "wagashi.back_workbench"),
        (16, 0, "read", "bookstore.reading_sofa"),
        (19, 0, "rest", "wagashi.back_workbench"),
    ],
    "kujo": [
        (7, 0, "patrol", "police_box.desk"),
        (10, 0, "patrol", "street.crossroad"),
        (12, 0, "eat", "police_box.desk"),
        (17, 0, "rest", "park.bench_01"),
        (23, 0, "sleep", "police_box.desk"),
    ],
}

# ══════════════════════════════════════════════════════════════
# BehaviorEngine
# ══════════════════════════════════════════════════════════════

class BehaviorEngine:
    """NPC 行为语义门面，运行时世界事实由 Unity 维护。"""

    def __init__(self, db: SQLiteClient, actions: dict, locations: dict):
        self.db = db
        self.actions = actions
        self.locations = locations
        self._task_catalog = NpcTaskCatalog(actions, locations)
        self._daily_schedule_planner = DailySchedulePlanner(
            self._task_catalog,
            self._call_daily_schedule_llm,
            memory_retrieve=self._retrieve_schedule_evidence,
        )
        self.prompt_assembler = PromptAssembler()

        # Routines: {npc_id: [(hour, minute, action, location), ...]}
        self._routines: dict[str, list[tuple[int, int, str, str]]] = {}
        self._load_routines()

        # 社交决策 Prompt（一次输出决定+开场白）
        self.SOCIAL_OPENING_PROMPT = """你是 {name}（{npc_id}），{personality}。
你现在 {action} @ {location}。你看到了 {other_name}（{other_id}）。

你们的关系: {bond_desc}（羁绊 {bond:.0%}），精力: {energy}/100

你想主动和TA说话吗？用 JSON:
{{"want_to_talk": true/false, "opening": "开场白(10字以内，不想说话则为空)"}}

只输出 JSON。"""

        self._last_day: int = 0

        # 摘要去重
        self._last_summary_minute: int = -1

        # LLM 每日计划: {npc_id: [{"time":"8:00","action":"...","location":"..."}, ...]}
        self._plans: dict[str, list[dict]] = {}
        # 新的一天标记
        self._planning_day: int = 0
        self._prepared_days: set[int] = set()
        self._daily_plan_lock = asyncio.Lock()
        self.schedule_snapshot_store = None

        # 日计划 Prompt
        self.PLAN_PROMPT = """你是 {name}，{age}岁，{occupation}。
性格: {personality}
说话风格: {speech}

商店街「樱桥通」的店铺和地点:
{locations_catalog}

你可用的行为: {actions_catalog}

你只能从以下已校验的任务@地点组合中选择:
{task_candidates}

你的日常参考（可以不照做，按你的性格自由决定）:
{routines_ref}

当前日期: {game_time}。请安排今天的日程。用JSON数组输出:
[{{"time":"HH:MM","action":"action_id","location":"location_id"}}]

## 你昨晚整理出的次日关注点
{plan_context}

规则:
- 必须用上面列出的 action_id 和 location_id
- 按时间顺序排列，覆盖你醒着的时间
- 符合你的性格——{personality_hint}
- 至少4条，最多8条
只输出 JSON 数组。"""

        self.REPLAN_PROMPT = """你是 {name}。原计划: {old_plan}
刚才和 {interrupted_by} 聊了天，现在 {game_time}。
只能使用这些任务@地点组合: {task_candidates}
接下来 2-3 件事做什么？用 JSON 数组:
[{{"time":"HH:MM","action":"action_id","location":"location_id"}}]
只输出 JSON。"""

        # WS 发送回调
        self._ws_sender: callable | None = None

        # NPC→NPC 对话回调（由 NpcDialogueManager 注册）
        self._npc_dialogue_callback: callable | None = None
        self._state_manager = None

    # ══════════════════════════════════════════════════════════
    # 初始化
    # ══════════════════════════════════════════════════════════

    def set_ws_sender(self, sender: callable):
        """设置 WebSocket 发送回调。"""
        self._ws_sender = sender

    def set_npc_dialogue_callback(self, callback: callable):
        """设置 NPC→NPC 对话回调（由 NpcDialogueManager 注册）。

        callback 签名: async def on_npc_social(npc_a: str, npc_b: str, location: str) -> None
        """
        self._npc_dialogue_callback = callback

    def set_state_manager(self, manager):
        """注入状态层，统一读取印象和写入即时状态。"""
        self._state_manager = manager

    def reset_prepared_days(self) -> None:
        """在新游戏冷启动后清除旧世界的日计划幂等缓存。"""
        self._prepared_days.clear()
        self._plans.clear()
        self._last_day = 0

    def is_npc_in_dialogue(self, npc_id: str) -> bool:
        """检查 NPC 是否正在参与任何对话（委托给 NpcDialogueManager）。"""
        if self._npc_dialogue_callback and hasattr(self._npc_dialogue_callback, '__self__'):
            mgr = self._npc_dialogue_callback.__self__
            if hasattr(mgr, 'is_npc_busy'):
                return mgr.is_npc_busy(npc_id)
        return False

    async def replan_from_unity_request(self, payload: dict, snapshot_store=None) -> dict:
        """仅按 Unity 权威剩余计划和冻结快照生成一个可整体替换的重规划结果。"""
        game_time = GameTimeSnapshot.from_dict(payload.get("game_time") or {})
        npc_id = str(payload.get("npc_id") or "")
        if not npc_id:
            raise ValueError("replan_npc_id_missing")
        remaining = tuple(
            DailyScheduleItem(
                candidate_id=str(item.get("candidate_id") or ""),
                action_id=str(item.get("action_id") or ""),
                location_id=str(item.get("location_id") or ""),
                target_person_id=str(item.get("target_person_id") or ""),
                planned_start_time=str(item.get("planned_start_time") or ""),
                necessity=str(item.get("necessity") or "optional"),
                primary_group=str(item.get("primary_group") or ""),
                groups=tuple(item.get("groups") or ()),
                evidence_ids=tuple(item.get("evidence_ids") or ()),
                execution_window_before_minutes=int(item.get("execution_window_before_minutes", 30)),
                execution_window_after_minutes=int(item.get("execution_window_after_minutes", 30)),
                source=str(item.get("source") or ""),
                miss_policy=str(item.get("miss_policy") or "skip_next"),
            )
            for item in (payload.get("remaining_schedule") or [])
        )
        snapshot = snapshot_store.require(str(payload.get("snapshot_id") or ""), int(payload.get("time_revision", -1)), int(payload.get("world_revision", -1))) if snapshot_store else None
        owner = NpcScheduleRequest(
            npc_id=npc_id,
            profile=self._load_npc_profile(npc_id),
            routines=tuple(self._routines.get(npc_id, ())),
            physical_state=snapshot.physical_state_for(npc_id) if snapshot else dict(payload.get("physical_state") or {}),
            plan_context=self._get_plan_context(npc_id),
            base_schedule_revision=int(payload.get("base_schedule_revision", 0)),
        )
        result = await self._daily_schedule_planner.replan_after_interaction(
            InteractionReplanRequest(
                context=BrainOperationContext(
                    operation_id=str(payload.get("operation_id") or f"schedule_replan_{uuid.uuid4().hex}"),
                    game_time=game_time,
                    world_revision=int(payload.get("world_revision", 0)),
                ),
                owner=owner,
                interaction_type=str(payload.get("interaction_type") or "runtime"),
                participant_ids=tuple(payload.get("participant_ids") or (npc_id,)),
                end_reason=str(payload.get("end_reason") or ""),
                interaction_summary=str(payload.get("interaction_summary") or ""),
                remaining_schedule=remaining,
            )
        )
        payload = [self._serialize_schedule_item(item) for item in result.items]
        self.db.save_daily_schedule_snapshot({
            "game_day": result.game_day, "npc_id": result.npc_id,
            "schedule_revision": result.schedule_revision,
            "payload_fingerprint": self._schedule_fingerprint(payload),
            "planner_version": result.planner_version, "operation_id": result.operation_id,
            "status": result.status, "failure_reason": result.failure_reason,
            "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        })
        return {
            "type": "NPC_DAILY_SCHEDULE_READY",
            "operation_id": result.operation_id,
            "npc_id": result.npc_id,
            "game_day": result.game_day,
            "schedule_revision": result.schedule_revision,
            "planner_version": result.planner_version,
            "items": payload,
            "status": result.status,
            "failure_reason": result.failure_reason,
        }

    def _load_routines(self):
        """从 profile JSON 加载 daily_rhythm.routines。

        如果 profile 中不存在 daily_rhythm 字段，
        回退到 DEFAULT_ROUTINES。
        """
        profiles_dir = Path(__file__).parent.parent.parent / "config" / "npc_profiles"
        for npc_id in ["sakura", "chihaya", "kazuha", "tatsunosuke", "kujo"]:
            profile_path = profiles_dir / f"{npc_id}.json"
            loaded = False
            if profile_path.exists():
                try:
                    with open(profile_path, "r", encoding="utf-8") as f:
                        profile = json.load(f)
                    daily = profile.get("daily_rhythm")
                    if daily and daily.get("routines"):
                        parsed = []
                        for entry in daily["routines"]:
                            time_str: str = entry["time"]
                            h, m = map(int, time_str.split(":"))
                            parsed.append((h, m, entry["action"], entry["location"]))
                        self._routines[npc_id] = parsed
                        loaded = True
                        logger.info(f"从 profile 加载 {npc_id} 的 {len(parsed)} 条 routines")
                except Exception as e:
                    logger.warning(f"加载 {npc_id} profile 失败: {e}")

            if not loaded:
                self._routines[npc_id] = DEFAULT_ROUTINES.get(npc_id, [])
                logger.info(f"{npc_id} 使用默认 routines ({len(self._routines[npc_id])} 条)")

    # ══════════════════════════════════════════════════════════
    # LLM 日计划
    # ══════════════════════════════════════════════════════════

    async def ensure_daily_plans(
        self,
        game_day: int,
        refresh_npc_day_state: bool,
        game_time: GameTimeSnapshot | None = None, snapshot_store=None, snapshot_id: str = "", time_revision: int = -1, world_revision: int = -1,
    ) -> None:
        """为指定游戏日幂等准备 NPC 状态与日计划，不重复调用 LLM。"""
        async with self._daily_plan_lock:
            if game_day in self._prepared_days:
                return
            # 进程重启后先从 SQLite 恢复，只有不存在权威快照时才调用 planner。
            persisted = [self.db.get_daily_schedule_snapshot(game_day, npc_id)
                         for npc_id in ("sakura", "chihaya", "kazuha", "tatsunosuke", "kujo")]
            if all(persisted):
                for snapshot in persisted:
                    items = json.loads(snapshot["payload_json"])
                    self._plans[snapshot["npc_id"]] = [
                        {"time": item.get("planned_start_time", ""), "action": item.get("action_id", ""),
                         "location": item.get("location_id", "")}
                        for item in items
                    ]
                    if self._ws_sender:
                        await self._ws_sender({
                            "type": "NPC_DAILY_SCHEDULE_READY",
                            "operation_id": snapshot["operation_id"],
                            "npc_id": snapshot["npc_id"], "game_day": game_day,
                            "schedule_revision": snapshot["schedule_revision"],
                            "planner_version": snapshot["planner_version"], "items": items,
                            "status": "idempotent_replay", "failure_reason": "",
                        })
                self._prepared_days.add(game_day)
                self._last_day = game_day
                return
            if refresh_npc_day_state:
                if self._state_manager:
                    for npc_id in ["sakura", "chihaya", "kazuha", "tatsunosuke", "kujo"]:
                        self._state_manager.begin_new_day(npc_id)
                else:
                    self.db.execute(
                        "UPDATE npc_states SET is_asleep = 0, energy = MIN(100.0, energy + 60.0)"
                    )
            frozen_time = game_time or GameTimeSnapshot(game_day, 8, 0, "sunny", 0)
            snapshot_store = snapshot_store or self.schedule_snapshot_store
            if snapshot_store is None: raise ValueError("schedule_snapshot_store_missing")
            snapshot = snapshot_store.require(snapshot_id, time_revision, world_revision) if snapshot_id else snapshot_store.require_latest()
            await self._plan_all_npcs(game_day, frozen_time, snapshot)
            self._prepared_days.add(game_day)
            self._last_day = game_day

    async def _plan_all_npcs(self, game_day: int, game_time: GameTimeSnapshot, snapshot):
        """通过统一 planner 并发生成并整体发布指定游戏日计划。"""
        npc_ids = ["sakura", "chihaya", "kazuha", "tatsunosuke", "kujo"]
        context = BrainOperationContext(
            operation_id=f"daily_schedule_{game_day}_{uuid.uuid4().hex[:12]}",
            game_time=game_time,
            world_revision=snapshot.world_revision,
        )
        owners = tuple(
            NpcScheduleRequest(
                npc_id=npc_id,
                profile=self._load_npc_profile(npc_id),
                routines=tuple(self._routines.get(npc_id, ())),
                physical_state=snapshot.physical_state_for(npc_id),
                plan_context=self._get_plan_context(npc_id),
            )
            for npc_id in npc_ids
        )
        batch = await self._daily_schedule_planner.prepare_day(
            DailyScheduleBatchRequest(context=context, owners=owners)
        )
        for result in batch.results:
            # 迁移期只读映射供尚未切换的上下文摘要使用，不再作为权威剩余计划。
            self._plans[result.npc_id] = [
                {"time": item.planned_start_time, "action": item.action_id, "location": item.location_id}
                for item in result.items
            ]
            if self._ws_sender:
                await self._ws_sender({
                    "type": "NPC_DAILY_SCHEDULE_READY",
                    "operation_id": result.operation_id,
                    "npc_id": result.npc_id,
                    "game_day": result.game_day,
                    "schedule_revision": result.schedule_revision,
                    "planner_version": result.planner_version,
                    "items": [self._serialize_schedule_item(item) for item in result.items],
                    "status": result.status,
                    "failure_reason": result.failure_reason,
                })
            payload = [self._serialize_schedule_item(item) for item in result.items]
            self.db.save_daily_schedule_snapshot({
                "game_day": result.game_day,
                "npc_id": result.npc_id,
                "schedule_revision": result.schedule_revision,
                "payload_fingerprint": self._schedule_fingerprint(payload),
                "planner_version": result.planner_version,
                "operation_id": result.operation_id,
                "status": result.status,
                "failure_reason": result.failure_reason,
                "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            })
        logger.info(f"日计划生成完成: {sum(1 for p in self._plans.values() if p)} NPCs")

    async def _call_daily_schedule_llm(self, messages: list[dict]) -> str:
        """在线程中调用同步供应商，避免阻塞协议事件循环。"""
        from ..dialogue import llm_client as llm_mod
        return await asyncio.to_thread(llm_mod.llm_client.chat, messages, temperature=0.7)

    @staticmethod
    def _retrieve_schedule_evidence(request):
        """经既有 retrieval facade 取得日程可追溯证据，不建立并行检索实现。"""
        from ..memory import retrieval as retrieval_module
        if retrieval_module.retrieval_engine is None:
            raise RuntimeError("schedule_memory_retrieval_unavailable")
        return retrieval_module.retrieval_engine.retrieve(request)

    def daily_schedule_diagnostics(self, operation_id: str = "", npc_id: str = "") -> list[dict]:
        """提供只读日程规划 trace，避免传输层耦合 planner 内部字段。"""
        return self._daily_schedule_planner.diagnostics.snapshot(operation_id, npc_id)

    @staticmethod
    def _serialize_schedule_item(item) -> dict:
        """把 planner DTO 转换为稳定 snake_case 协议字段。"""
        return {
            "candidate_id": item.candidate_id,
            "action_id": item.action_id,
            "location_id": item.location_id,
            "target_person_id": item.target_person_id,
            "planned_start_time": item.planned_start_time,
            "execution_window_before_minutes": item.execution_window_before_minutes,
            "execution_window_after_minutes": item.execution_window_after_minutes,
            "necessity": item.necessity,
            "primary_group": item.primary_group,
            "groups": list(item.groups),
            "evidence_ids": list(item.evidence_ids),
            "source": item.source,
            "miss_policy": item.miss_policy,
        }

    @staticmethod
    def _schedule_fingerprint(items: list[dict]) -> str:
        """按完整 DTO 计算稳定指纹，避免同 revision 内容漂移。"""
        encoded = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    # ══════════════════════════════════════════════════════════
    # 计划辅助
    # ══════════════════════════════════════════════════════════

    def _get_state(self, npc_id: str) -> dict | None:
        """统一读取 NPC 状态。"""
        if self._state_manager and hasattr(self._state_manager, "get_state"):
            try:
                return self._state_manager.get_state(npc_id)
            except Exception as e:
                logger.debug(f"状态读取失败 ({npc_id}): {e}")
        return self.db.fetchone("SELECT * FROM npc_states WHERE npc_id = ?", (npc_id,))

    def _get_impression_bundle(self, owner_id: str, target_id: str) -> dict:
        """统一读取熟人印象。"""
        if self._state_manager and hasattr(self._state_manager, "get_impression_bundle"):
            try:
                return self._state_manager.get_impression_bundle(owner_id, target_id)
            except Exception as e:
                logger.debug(f"印象读取失败 ({owner_id}->{target_id}): {e}")
        target_name = self._get_display_name(target_id)
        return {
            "text": f"对{target_name}目前没有特别鲜明的印象。",
            "speech_hint": "先按平常语气交流。",
            "approach_bias": 0.0,
        }

    def _get_plan_context(self, npc_id: str) -> str:
        """读取夜间生成的次日计划摘要。"""
        if self._state_manager and hasattr(self._state_manager, "get_next_day_plan_context"):
            try:
                return self._state_manager.get_next_day_plan_context(npc_id)
            except Exception as e:
                logger.debug(f"计划摘要读取失败 ({npc_id}): {e}")
        row = self.db.fetchone("SELECT next_day_plan_context FROM npc_states WHERE npc_id = ?", (npc_id,))
        return row.get("next_day_plan_context", "") if row else ""

    def _load_npc_profile(self, npc_id: str) -> dict:
        """加载 NPC profile JSON"""
        import json as _json
        from pathlib import Path
        if npc_id == "player":
            return load_player_profile()
        path = Path(__file__).parent.parent.parent / "config" / "npc_profiles" / f"{npc_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return _json.load(f)
        return {"name": npc_id}

    def _get_display_name(self, entity_id: str) -> str:
        """返回玩家或 NPC 在 prompt 中使用的显示名。"""
        if entity_id == "player":
            return get_player_display_name()
        profile = self._load_npc_profile(entity_id)
        return profile.get("name", entity_id)

    def _build_locations_catalog(self) -> str:
        """构建地点目录摘要"""
        zones = self.locations.get("zones", {})
        lines = []
        for zname, zdata in list(zones.items())[:9]:
            label = zdata.get("label", zname)
            spots = ", ".join(zdata.get("spots", [])[:3])
            lines.append(f"  {zname}（{label}）: {spots}")
        return "\n".join(lines)[:800]

    def _build_actions_catalog(self) -> str:
        """构建行为目录摘要"""
        cats = self.actions.get("actions", {})
        lines = []
        for cname, acts in cats.items():
            ids = [a["id"] for a in acts if a["id"] in self._task_catalog.action_ids]
            if ids:
                lines.append(f"  {cname}: {', '.join(ids)}")
        return "\n".join(lines)[:600]

    def _build_task_candidates(self, npc_id: str) -> str:
        """构建经过 action-location-role affordance 校验的计划候选。"""
        lines = []
        for action_id in sorted(self._task_catalog.action_ids):
            locations = self._task_catalog.allowed_locations(npc_id, action_id)
            if locations:
                lines.append(f"  {action_id}: {', '.join(locations)}")
        return "\n".join(lines)[:1800]

    def _format_routines_ref(self, npc_id: str) -> str:
        """格式化日常参考"""
        routines = self._routines.get(npc_id, [])
        if not routines:
            return "（无参考日程）"
        return "\n".join(f"  {h:02d}:{m:02d} {a} @ {l}"
                        for h, m, a, l in routines[:6])

    def _personality_hint(self, name: str, profile: dict) -> str:
        """根据性格生成行为提示"""
        p = profile.get("personality", "")
        if "社恐" in p or "自卑" in p:
            return "你不太喜欢社交，尽量待在熟悉的地方，避免人群"
        if "热血" in p or "大大咧咧" in p:
            return "你精力充沛，喜欢到处走动，乐于帮助别人"
        if "温柔" in p or "内敛" in p:
            return "你喜欢安静的环境，做事认真，偶尔会和亲近的人分享心事"
        if "颓废" in p or "脱力" in p:
            return "你做什么都提不起劲，喜欢在公园或河边发呆，偶尔喂猫"
        if "冷静" in p or "浪漫" in p:
            return "你喜欢安静地看书，偶尔深夜出门，会注意到别人忽略的细节"
        return "按你的性格自然行动"

    def _time_cmp(self, t1: str, t2: str) -> int:
        """比较 HH:MM 时间字符串: -1 0 1"""
        return -1 if t1 < t2 else (1 if t1 > t2 else 0)

    @property
    def _valid_action_ids(self) -> set:
        """所有合法 action_id"""
        if not hasattr(self, '_cached_actions'):
            ids = set()
            ids.update(self._task_catalog.action_ids)
            self._cached_actions = ids
        return self._cached_actions

    @property
    def _valid_location_ids(self) -> set:
        """所有合法 location_id"""
        if not hasattr(self, '_cached_locations'):
            ids = set()
            ids.update(self._task_catalog.location_ids)
            self._cached_locations = ids
        return self._cached_locations

    def _fallback_plan(self, npc_id: str) -> list[dict]:
        """LLM 失败时的回退计划（使用 profile routines）"""
        routines = self._routines.get(npc_id, [])
        return [{"time": f"{h:02d}:{m:02d}", "action": a, "location": l}
                for h, m, a, l in routines[:6]]

    def get_remaining_plan_summary(self, npc_id: str, limit: int = 3) -> str:
        """返回 NPC 当前剩余计划的自然语言摘要。"""
        remaining = self._plans.get(npc_id, [])
        if not remaining or len(remaining) <= 1:
            return ""

        from ..dialogue.prompt_builder import _act_name, _loc_name

        items = [
            f"{step['time']} {_act_name(step['action'])}去{_loc_name(step['location'])}"
            for step in remaining[:limit]
        ]
        return "接下来: " + "，".join(items)

    async def _llm_decide_talk(self, npc_id: str, other_id: str,
                                 location: str) -> bool:
        """LLM 判断 NPC 是否想主动发起对话"""
        state = self._get_state(npc_id)
        if not state:
            return False
        profile = self._load_npc_profile(npc_id)
        name = profile.get("name", npc_id)
        other_name = self._get_display_name(other_id)
        impression = self._get_impression_bundle(npc_id, other_id)

        prompt = self.prompt_assembler.build("npc_social_intent", {
            "profile": profile, "name": name, "npc_id": npc_id,
            "npc_tags": format_npc(profile), "current_action": state.get("current_action") or "stand",
            "location": location, "other_name": other_name, "other_id": other_id,
            "impression_text": impression["text"], "speech_hint": impression["speech_hint"],
            "approach_bias": float(impression["approach_bias"]),
            "energy": float(state.get("energy", 80)), "sociability": float(state.get("sociability", 50)),
        })
        try:
            from ..dialogue import llm_client as llm_mod
            raw = llm_mod.llm_client.chat(
                prompt,
                temperature=0.6)
            data = json.loads(raw.strip().lstrip("```json").rstrip("```").strip())
            return data.get("want_to_talk", False)
        except Exception:
            return impression["approach_bias"] > 0.15 and float(state.get("sociability", 50)) > 35.0

    @staticmethod
    def _bond_desc(bond: float) -> str:
        if bond >= 0.8: return "亲密信任"
        if bond >= 0.6: return "喜欢"
        if bond >= 0.4: return "友好"
        if bond >= 0.2: return "认识"
        return "陌生"

    # ══════════════════════════════════════════════════════════
    # Bond 读取
    # ══════════════════════════════════════════════════════════

    def _get_bond(self, npc_a: str, npc_b: str) -> float:
        """读取两个 NPC 之间的 bond 值。

        尝试 (a,b) 和 (b,a)，找不到返回默认值 0.5。
        """
        for owner, target in [(npc_a, npc_b), (npc_b, npc_a)]:
            row = self.db.fetchone(
                "SELECT bond FROM npc_bonds WHERE owner_id=? AND target_id=?",
                (owner, target))
            if row:
                return float(row["bond"])
        return 0.5

    # ══════════════════════════════════════════════════════════
    # 状态摘要
    # ══════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════
    # 计划匹配
    # ══════════════════════════════════════════════════════════

    def _match_plan_step(self, plan: list[dict], hour: int, minute: int) -> dict | None:
        """从计划中匹配当前时间应执行的步骤（±1 分钟容差）。
        返回第一条匹配的步骤。调用方负责从 plan 中 remove 该步骤。
        """
        for step in plan:
            t = step.get("time", "99:99")
            diff = abs((hour * 60 + minute) - (int(t[:2]) * 60 + int(t[3:5])))
            if diff <= 1:
                return step
        return None

    def handle_runtime_event(self, msg: dict) -> dict:
        """幂等接收 Unity 已裁决的运行时终态，不再驱动位置、重试或任务监督。"""
        event_id = str(msg.get("event_id") or "")
        npc_id = str(msg.get("npc_id") or "")
        if not event_id or not npc_id:
            return {"accepted": False, "reason": "runtime_event_identity_missing"}
        seen = getattr(self, "_runtime_event_ids", set())
        if event_id in seen:
            return {"accepted": True, "reason": "duplicate_runtime_event"}
        seen.add(event_id)
        self._runtime_event_ids = seen
        result = str(msg.get("result") or "")
        if result in {"succeeded", "failed", "cancelled"}:
            logger.info("Unity 运行时事件: npc=%s result=%s event=%s", npc_id, result, event_id)
        return {"accepted": True, "reason": "runtime_event_recorded"}
