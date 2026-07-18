"""固定玩家目标的午夜印象刷新与次日基准策略。"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from ..dialogue import llm_client as llm_module
from ..dialogue.player_name import get_player_display_name, get_player_name_candidates
from ..memory.retrieval_contracts import (
    RecallIntent,
    RelationFacet,
    RetrievalDirection,
    RetrievalRequest,
    Theme,
    TimeScope,
)
from ..prompting import PromptAssembler
from ..prompting.tag_formatter import format_npc

logger = logging.getLogger("sakurabashi.player_impression")

PLAYER_TARGET_ID = "player"
MAX_PLAYER_IMPRESSION_WORKERS = 5


def _clamp(value: float, low: float, high: float) -> float:
    """把数值限制到闭区间。"""
    return max(low, min(high, value))


@dataclass(frozen=True)
class PlayerImpressionInput:
    """保存事件提取前冻结的单个 NPC 玩家印象输入。"""

    order: int
    owner_id: str
    owner_name: str
    personality: str
    lingering_concern: str
    recent_memories: str
    graph_memories: str
    previous: str
    retrieval_trace_id: str = ""


@dataclass(frozen=True)
class PlayerImpressionOutput:
    """保存单个玩家印象的纯生成结果。"""

    input: PlayerImpressionInput
    baseline: dict
    used_fallback: bool = False
    failure_reason: str = ""


@dataclass
class PlayerImpressionBatchResult:
    """聚合玩家印象生成阶段的计数与耗时。"""

    outputs: list[PlayerImpressionOutput] = field(default_factory=list)
    planned_count: int = 0
    success_count: int = 0
    fallback_count: int = 0
    failed_owner_ids: list[str] = field(default_factory=list)
    elapsed_sec: float = 0.0


def build_nightly_player_direction() -> RetrievalDirection:
    """构造固定玩家目标的受控夜间检索方向。"""
    player_name = get_player_display_name()
    return RetrievalDirection(
        entity_mentions=list(dict.fromkeys((player_name, *get_player_name_candidates()))),
        themes=[
            Theme.RELATIONSHIP.value,
            Theme.RECENT_ACTIVITY.value,
            Theme.PAST_EVENT.value,
            Theme.EMOTION.value,
        ],
        relation_facets=[
            RelationFacet.AFFINITY.value,
            RelationFacet.SHARED_EVENT.value,
            RelationFacet.IMPRESSION_BASIS.value,
        ],
        time_scope=TimeScope.RECENT.value,
        recall_intent=RecallIntent.COMPARE_RELATIONSHIP.value,
        retrieval_query=f"回忆与{player_name}的关系、近期互动、共同事件和印象依据",
        query_constraints=["relationship", "recent", "past_event"],
    )


class PlayerImpressionRefresher:
    """冻结、生成并提交固定玩家目标的午夜印象。"""

    def __init__(self, state_manager, retrieval, npc_ids: list[str]):
        """注入兼容状态 facade、正式检索器和稳定 NPC 列表。"""
        self.state_manager = state_manager
        self.db = state_manager.db
        self.retrieval = retrieval
        self.npc_ids = [npc_id for npc_id in npc_ids if npc_id != PLAYER_TARGET_ID]
        self.prompt_assembler = PromptAssembler()

    def prepare_inputs(self, game_day: int) -> list[PlayerImpressionInput]:
        """在事件提取前冻结五名 NPC 的玩家印象输入与路由结果。"""
        prepared: list[PlayerImpressionInput] = []
        direction = build_nightly_player_direction()
        for order, owner_id in enumerate(self.npc_ids):
            profile = self.state_manager._load_profile(owner_id)
            state = self.state_manager.get_state(owner_id) or {}
            recent = self.state_manager._recent_target_memories(owner_id, PLAYER_TARGET_ID, game_day)
            previous = self.state_manager.get_impression_bundle(owner_id, PLAYER_TARGET_ID)["text"]
            request = RetrievalRequest(
                npc_id=owner_id,
                conversation_participant_ids=[PLAYER_TARGET_ID],
                query_text=direction.retrieval_query,
                location_id="nightly_reflection",
                game_time=f"第{game_day}天 24:00",
                mode="nightly_impression",
                direction_override=direction,
                direction_source="nightly_fixed_player",
            )
            result = self.retrieval.retrieve(request)
            prepared.append(PlayerImpressionInput(
                order=order,
                owner_id=owner_id,
                owner_name=profile.get("name", owner_id),
                personality=profile.get("personality", ""),
                lingering_concern=state.get("lingering_concern", ""),
                recent_memories=recent,
                graph_memories=result.rebuilt_context or "（图中没有明显相关片段）",
                previous=previous,
                retrieval_trace_id=str(result.diagnostics.get("retrieval_trace_id", "")),
            ))
        return prepared

    def generate(self, inputs: list[PlayerImpressionInput]) -> PlayerImpressionBatchResult:
        """有界并发生成玩家印象，工作线程不执行数据库写入。"""
        started = time.perf_counter()
        outputs: list[PlayerImpressionOutput] = []
        with ThreadPoolExecutor(
            max_workers=min(MAX_PLAYER_IMPRESSION_WORKERS, max(1, len(inputs))),
            thread_name_prefix="player-impression",
        ) as pool:
            futures = {pool.submit(self._generate_one, item): item for item in inputs}
            for future in as_completed(futures):
                item = futures[future]
                try:
                    outputs.append(future.result())
                except Exception as error:
                    logger.warning("玩家印象生成失败 (%s): %s", item.owner_id, error)
                    outputs.append(PlayerImpressionOutput(
                        input=item,
                        baseline=self.state_manager._fallback_impression(
                            get_player_display_name(), item.recent_memories, item.graph_memories, item.previous,
                        ),
                        used_fallback=True,
                        failure_reason=str(error),
                    ))
        outputs.sort(key=lambda item: item.input.order)
        fallback_owners = [item.input.owner_id for item in outputs if item.used_fallback]
        return PlayerImpressionBatchResult(
            outputs=outputs,
            planned_count=len(inputs),
            success_count=len(outputs) - len(fallback_owners),
            fallback_count=len(fallback_owners),
            failed_owner_ids=fallback_owners,
            elapsed_sec=time.perf_counter() - started,
        )

    def _generate_one(self, item: PlayerImpressionInput) -> PlayerImpressionOutput:
        """调用一次夜间印象 LLM 并收口为稳定字段。"""
        profile = {"personality": item.personality or "（未定义）"}
        prompt = self.prompt_assembler.build("nightly_impression", {
            "profile": profile,
            "owner_name": item.owner_name,
            "npc_tags": format_npc(profile),
            "lingering_concern": item.lingering_concern or "无",
            "target_name": get_player_display_name(),
            "recent_memories": item.recent_memories,
            "graph_memories": item.graph_memories,
            "previous": item.previous or "（无）",
        })
        raw = llm_module.llm_client.chat(
            [
                {"role": "system", "content": "你负责把零散记忆压缩成稳定、简短的熟人印象。"},
                {"role": "user", "content": prompt[0]["content"]},
            ],
            temperature=0.45,
        )
        data = json.loads(raw.strip().lstrip("```json").rstrip("```").strip())
        baseline = {
            "baseline_impression": str(data.get("baseline_impression", "")).strip() or f"对{get_player_display_name()}的感觉暂时没有明显变化。",
            "speech_hint": str(data.get("speech_hint", "")).strip() or "先按平常语气交流。",
            "approach_bias": round(_clamp(float(data.get("approach_bias", 0.0)), -1.0, 1.0), 2),
        }
        return PlayerImpressionOutput(input=item, baseline=baseline)

    def _generate_fallback_output(self, item: PlayerImpressionInput, reason: str) -> PlayerImpressionOutput:
        """构造协调器可复用的单目标启发式 fallback。"""
        return PlayerImpressionOutput(
            input=item,
            baseline=self.state_manager._fallback_impression(
                get_player_display_name(), item.recent_memories, item.graph_memories, item.previous,
            ),
            used_fallback=True,
            failure_reason=reason,
        )

    def commit(self, batch: PlayerImpressionBatchResult, game_day: int) -> None:
        """在协调线程顺序提交玩家印象并只清空玩家关系 delta。"""
        for item in batch.outputs:
            baseline = item.baseline
            self.db.execute(
                """INSERT INTO npc_impressions
                   (owner_id, target_id, baseline_impression, speech_hint, approach_bias,
                    delta_note, delta_bias, updated_game_day, updated_at)
                   VALUES (?, 'player', ?, ?, ?, '', 0.0, ?, datetime('now'))
                   ON CONFLICT(owner_id, target_id) DO UPDATE SET
                       baseline_impression = excluded.baseline_impression,
                       speech_hint = excluded.speech_hint,
                       approach_bias = excluded.approach_bias,
                       delta_note = '', delta_bias = 0.0,
                       updated_game_day = excluded.updated_game_day,
                       updated_at = datetime('now')""",
                (item.input.owner_id, baseline["baseline_impression"], baseline["speech_hint"], baseline["approach_bias"], game_day),
            )

    def refresh_next_day_baselines(self, game_day: int) -> None:
        """刷新次日状态，社交基准只使用玩家印象而不平均 NPC-NPC 基线。"""
        for owner_id in self.npc_ids:
            profile = self.state_manager._load_profile(owner_id)
            state = self.state_manager.get_state(owner_id)
            if not state:
                continue
            player_row = self.db.fetchone(
                "SELECT approach_bias FROM npc_impressions WHERE owner_id = ? AND target_id = 'player'",
                (owner_id,),
            ) or {}
            emotion_baseline = self.state_manager._resolve_emotion(
                state.get("emotion_baseline", "平静"),
                float(state.get("emotion_delta", 0.0)) * 0.4,
                state.get("lingering_concern", ""),
            )
            sociability_baseline = calculate_sociability_baseline(
                float(profile.get("social_base", 50.0)),
                float(state.get("sociability_delta", 0.0)),
                float(player_row.get("approach_bias", 0.0)),
            )
            concern = self.state_manager._derive_lingering_concern(owner_id, state)
            plan_context = self.state_manager._build_plan_context(owner_id, game_day)
            self.db.execute(
                """UPDATE npc_states
                   SET emotion_baseline = ?, sociability_baseline = ?, lingering_concern = ?,
                       next_day_plan_context = ?, updated_at = datetime('now')
                   WHERE npc_id = ?""",
                (emotion_baseline, sociability_baseline, concern, plan_context, owner_id),
            )


def calculate_sociability_baseline(social_base: float, daily_delta: float, player_bias: float) -> float:
    """按集中权重计算不受陈旧 NPC-NPC 印象影响的次日社交基准。"""
    bounded_player_bias = _clamp(player_bias, -1.0, 1.0)
    return _clamp(social_base + bounded_player_bias * 12.0 + daily_delta * 0.3, 0.0, 100.0)
