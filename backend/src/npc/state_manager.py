"""
NPC 状态管理 — 即时状态 + 羁绊度 + 图初始化。
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import uuid
import logging
import os
from pathlib import Path

from ..config import config
from ..database.sqlite_client import SQLiteClient
from ..dialogue import llm_client as _llm_module
from ..dialogue.player_name import get_player_display_name, get_player_name_candidates, render_player_tokens
from ..memory.edge_semantics import initial_relationship_clarity, resolve_edge_clarity
from ..memory.initial_knowledge import (
    KnowledgeRelationshipContext,
    load_initial_knowledge,
    project_initial_knowledge,
)
from ..prompting import PromptAssembler
from ..prompting.tag_formatter import format_npc

logger = logging.getLogger("sakurabashi.state")


def _memory_trace_enabled() -> bool:
    return os.getenv("SAKURA_MEMORY_TRACE", "").strip().lower() in {"1", "true", "yes", "on"}

# 所有 NPC 的完整 ID 列表
ALL_NPC_IDS = ["sakura", "chihaya", "kazuha", "tatsunosuke", "kujo"]
TARGET_IDS = ["player"] + ALL_NPC_IDS  # NPC 可关联的对象（含玩家）

# 默认 decay_rate 映射
DECAY_RATES = {
    "self": 0.0,
    "person": 0.002,
    "event": 0.01,
    "time_exact": 0.05,
    "time_vague": 0.01,
    "time_cycle": 0.005,
    "place_exact": 0.015,
    "place_vague": 0.008,
    "emotion": 0.005,
    "sensory": 0.03,
    "item": 0.015,
    "quote": 0.06,
    "reflection": 0.008,
}

EMOTION_ORDER = ["低落", "紧张", "平静", "开心"]
NIGHTLY_IMPRESSION_MAX_WORKERS = 6

IMPRESSION_PROMPT = """你在为 NPC 生成对熟人的基准印象。

## NPC
名字: {owner_name}
性格: {personality}
当前心事: {lingering_concern}

## 对方
名字: {target_name}

## 近期互动
{recent_memories}

## 图中相关记忆
{graph_memories}

请输出 JSON：
{{
  "baseline_impression": "1-2句话，概括现在怎么看这个人",
  "speech_hint": "一句话，说明和这个人说话时的语气",
  "approach_bias": -1.0到1.0的小数,
  "emotion_baseline": "低落/紧张/平静/开心 之一",
  "lingering_concern": "如果这个人让你牵挂什么，写一句；没有就写空字符串"
}}

要求：
- impression 偏主观感受，不要复述全部事件
- speech_hint 要能直接用于对白语气
- approach_bias > 0 表示更想接近，< 0 表示更想回避
- 只输出 JSON
"""


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class StateManager:
    """NPC 状态与图初始化 v0.6"""

    def __init__(self, db: SQLiteClient, lancedb=None):
        self.db = db
        self.lancedb = lancedb
        self.prompt_assembler = PromptAssembler()
        self._lance_pending: list[dict] = []
        self._retrieval = None
        self._initial_knowledge_facts = load_initial_knowledge(
            Path(__file__).resolve().parents[2] / "config" / "initial_knowledge.json",
            known_ids=set(TARGET_IDS),
        )
        self._initial_knowledge_context = KnowledgeRelationshipContext(
            community_observer_ids=frozenset(TARGET_IDS),
        )

    def set_retrieval(self, retrieval) -> None:
        """注入图检索器，供夜间印象刷新复用多跳路由。"""
        self._retrieval = retrieval

    # ═══════════════════════════════════════════
    # 冷启动
    # ═══════════════════════════════════════════

    def cold_start(self):
        """新游戏初始化：清空旧数据 + 创建初始状态 + 初始图"""
        logger.info("冷启动: 初始化所有 NPC 状态和初始图...")

        # 1. 清空（确保幂等）
        self.db.execute("DELETE FROM memory_edges")
        self.db.execute("DELETE FROM memory_nodes")
        self.db.execute("DELETE FROM npc_states")
        self.db.execute("DELETE FROM npc_bonds")
        self.db.execute("DELETE FROM npc_impressions")
        self.db.execute("DELETE FROM short_term_memories")
        self.db.execute("DELETE FROM player_memories")
        self.db.execute("DELETE FROM memory_initial_projections")
        logger.info("  旧数据已清空")
        if self.lancedb and hasattr(self.lancedb, "clear_all"):
            self.lancedb.clear_all()
            logger.info("  LanceDB 旧向量已清空")

        # 2. 为每个 NPC 初始化
        for npc_id in ALL_NPC_IDS:
            profile = self._load_profile(npc_id)
            self._init_npc_state(npc_id, profile)
            self._init_initial_bonds(npc_id, profile)
            self._seed_initial_impressions(npc_id, profile)
            self._init_graph(npc_id, profile)

        # 3. 玩家初始记忆
        self._init_player_memories()

        # 4. 游戏状态
        self.db.execute(
            "UPDATE game_state SET game_day=1, game_hour=8, game_minute=0, "
            "weather='sunny', player_location='player_cafe.doorway', "
            "updated_at=datetime('now') WHERE id=1"
        )

        # 5. 刷新 LanceDB 向量（BGE encode 后写入）
        self._flush_lance()

        logger.info("冷启动完成")

    def _flush_lance(self):
        """批量编码并写入 LanceDB"""
        if not self._lance_pending or not self.lancedb:
            self._lance_pending.clear()
            return
        try:
            from ..memory.embedding import encode_batch
            texts = [n["value"] for n in self._lance_pending]
            vecs = encode_batch(texts)
            if vecs is not None:
                for i, n in enumerate(self._lance_pending):
                    n["vector"] = vecs[i].tolist()
            # 按 NPC 分组写入
            by_npc: dict[str, list] = {}
            for n in self._lance_pending:
                # 从节点元数据优先读取 NPC；旧节点仍兼容 node_sakura_xxx 格式。
                npc = n.get("npc_id")
                if not npc:
                    parts = n["node_id"].split("_")
                    npc = parts[1] if len(parts) > 1 else "unknown"
                by_npc.setdefault(npc, []).append(n)
            for npc, nodes in by_npc.items():
                self.lancedb.upsert_nodes(npc, nodes)
            logger.info(f"LanceDB 初始化: {len(self._lance_pending)} 节点写入")
        except Exception as e:
            logger.warning(f"LanceDB 初始化跳过: {e}")
        self._lance_pending.clear()

    def _load_profile(self, npc_id: str) -> dict:
        """加载 NPC 配置文件"""
        path = Path(__file__).resolve().parent.parent.parent
        path = path / "config" / "npc_profiles" / f"{npc_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        logger.warning(f"NPC 配置不存在: {path}, 使用默认值")
        return {
            "npc_id": npc_id, "name": npc_id, "age": 20, "gender": "unknown",
            "occupation": "未知", "personality": "", "speech_style": "",
            "social_base": 50, "energy_base": 80, "base_budget": 5,
            "strategy_weights": {"breadth": 0.25, "depth": 0.25, "best": 0.25, "easy": 0.25},
            "core_memories": [], "daily_rhythm": {"wake": "7:00", "sleep": "23:00", "routines": []},
            "initial_bonds": {t: 0.0 for t in TARGET_IDS if t != npc_id},
            "initial_impression_traits": {},
        }

    def _init_npc_state(self, npc_id: str, profile: dict):
        """写入 NPC 即时状态"""
        self.db.execute(
            """INSERT OR REPLACE INTO npc_states
               (npc_id, emotion, emotion_baseline, emotion_delta, energy,
                sociability, sociability_baseline, sociability_delta,
                current_need, lingering_concern, next_day_plan_context,
                current_location, current_action, is_first_encounter, is_asleep)
               VALUES (?, '平静', '平静', 0.0, ?, ?, ?, 0.0,
                       NULL, '', '', ?, NULL, 1, 0)""",
            (npc_id,
             profile.get("energy_base", 80.0),
             profile.get("social_base", 50.0),
             profile.get("social_base", 50.0),
             self._default_location(npc_id)),
        )

    def _init_initial_bonds(self, npc_id: str, profile: dict):
        """写入 NPC 对所有人的初始羁绊度"""
        bonds = profile.get("initial_bonds", {})
        for target_id in TARGET_IDS:
            if target_id == npc_id:
                continue
            bond_val = bonds.get(target_id, 0.0)
            # confide_level 从 bond 推导
            if bond_val >= 0.7:
                confide = 3
            elif bond_val >= 0.5:
                confide = 2
            elif bond_val >= 0.2:
                confide = 1
            else:
                confide = 0
            self.db.execute(
                """INSERT OR REPLACE INTO npc_bonds (owner_id, target_id, bond, confide_level)
                   VALUES (?, ?, ?, ?)""",
                (npc_id, target_id, bond_val, confide),
            )

    def _seed_initial_impressions(self, npc_id: str, profile: dict):
        """为每个熟人写入初始印象，供白天轻决策读取。"""
        initial_traits = profile.get("initial_impression_traits", {}) or {}
        bonds = profile.get("initial_bonds", {}) or {}

        for target_id in TARGET_IDS:
            if target_id == npc_id:
                continue

            target_name = self._get_npc_name(target_id)
            trait_hint = initial_traits.get(target_id, "")
            closeness = float(bonds.get(target_id, 0.0))
            approach_bias = round(_clamp((closeness - 0.5) * 1.2, -0.8, 0.8), 2)

            if closeness >= 0.7:
                baseline = f"和{target_name}很熟，见面时通常比较放松。"
                speech_hint = "语气可以自然、亲近一点。"
            elif closeness >= 0.4:
                baseline = f"对{target_name}算是熟悉，愿意正常来往。"
                speech_hint = "语气自然，不必过分拘谨。"
            elif closeness >= 0.1:
                baseline = f"认识{target_name}，但还在观察对方。"
                speech_hint = "语气礼貌，保持一点分寸。"
            else:
                baseline = f"对{target_name}还不算熟，暂时只维持普通来往。"
                speech_hint = "语气客气，先别太亲近。"

            if trait_hint:
                baseline += f" 直觉上觉得TA{trait_hint}。"

            self.db.execute(
                """INSERT OR REPLACE INTO npc_impressions
                   (owner_id, target_id, baseline_impression, speech_hint,
                    approach_bias, delta_note, delta_bias, updated_game_day)
                   VALUES (?, ?, ?, ?, ?, '', 0.0, 1)""",
                (npc_id, target_id, baseline, speech_hint, approach_bias),
            )

    def _init_graph(self, npc_id: str, profile: dict):
        """创建 NPC 初始图 v0.6: SQLite(ID+边) + LanceDB(数据+向量)"""
        game_time = "第1天 08:00"
        lance_batch = []  # 批量写 LanceDB
        person_count = 0
        core_event_count = 0
        shared_memory_count = 0
        init_edge_count = 0

        # 1. "我" 节点 (importance=1.0 核心记忆)
        self_id = self._make_node_id(npc_id)
        self.db.insert_node({"id": self_id, "subject_id": npc_id, "created_at_game_time": game_time})
        lance_batch.append(self._make_lance_node(self_id, "self", "我", importance=1.0))

        # 2. 人物节点 + relationship 边
        bonds = profile.get("initial_bonds", {})
        person_node_ids: dict[str, str] = {}
        for target_id in TARGET_IDS:
            if target_id == npc_id:
                continue
            target_name = self._get_npc_name(target_id)
            person_id = self._make_node_id(npc_id)
            self.db.insert_node({"id": person_id, "subject_id": npc_id, "created_at_game_time": game_time})
            lance_batch.append(self._make_lance_node(person_id, "person", target_name, importance=0.9))
            person_count += 1
            person_node_ids[target_id] = person_id

            # relationship 边: bond 只微调核心人物基础认知 clarity。
            bond_val = bonds.get(target_id, 0.0)
            clarity_ab, clarity_ba = initial_relationship_clarity(
                recognition_importance=0.9,
                bond=bond_val,
                is_core_person=True,
            )
            self.db.insert_edge({
                "id": f"edge_rel_{npc_id}_{target_id}",
                "node_a": self_id, "node_b": person_id,
                "type": "relationship",
                "clarity_ab": clarity_ab,
                "clarity_ba": clarity_ba,
                "target_importance": 0.9,
                "created_at_game_time": game_time,
            })
            init_edge_count += 1

        # 3. 初始共享长期记忆：玩家背景 / 商店街背景
        for shared_memory in self._build_initial_shared_memories(npc_id):
            init_edge_count += self._seed_initial_memory_node(
                npc_id=npc_id,
                game_time=game_time,
                lance_batch=lance_batch,
                self_id=self_id,
                person_node_ids=person_node_ids,
                memory=shared_memory,
            )
            shared_memory_count += 1

        # 4. NPC 个人旧有核心记忆
        for cm in profile.get("core_memories", []):
            init_edge_count += self._seed_initial_memory_node(
                npc_id=npc_id,
                game_time=game_time,
                lance_batch=lance_batch,
                self_id=self_id,
                person_node_ids=person_node_ids,
                memory=cm,
            )
            core_event_count += 1

        # 批量写 LanceDB (不阻塞，后台执行)
        if hasattr(self, '_lance_pending'):
            self._lance_pending.extend(lance_batch)
        else:
            self._lance_pending = list(lance_batch)
        if _memory_trace_enabled():
            logger.info(
                "[记忆诊断] 初始图 npc=%s person_nodes=%s shared_memories=%s core_events=%s init_edges=%s pending_lance_nodes=%s",
                npc_id,
                person_count,
                shared_memory_count,
                core_event_count,
                init_edge_count,
                len(lance_batch),
            )

    # 为了让玩家背景和商店街背景成为真正的长期真相源，冷启动时统一入图。
    def _build_initial_shared_memories(self, npc_id: str) -> list[dict]:
        """返回当前观察者有权知道的初始事实投影。"""
        result = project_initial_knowledge(
            self._initial_knowledge_facts,
            npc_id,
            self._initial_knowledge_context,
        )
        return [
            {
                "projection_id": item.projection_id,
                "observer_id": item.observer_id,
                "source_fact_id": item.source_fact_id,
                "fact_type": item.fact_type,
                "type": item.node_type,
                "value": item.value,
                "subject_ids": list(item.subject_ids),
                "location_ids": list(item.location_ids),
                "source_type": item.source_type,
                "confidence": item.confidence,
                "importance": item.importance,
                "created_day": item.created_day,
                "visibility_rule": item.visibility_rule,
                "visibility_reason": item.visibility_reason,
            }
            for item in result.projections
        ]

    # 统一初始记忆入图逻辑，避免“共享背景”和“个人旧事”走出两套结构。
    def _seed_initial_memory_node(
        self,
        npc_id: str,
        game_time: str,
        lance_batch: list[dict],
        self_id: str,
        person_node_ids: dict[str, str],
        memory: dict,
    ) -> int:
        """把一条初始长期记忆写入 SQLite 图和 LanceDB。"""
        memory_id = memory.get("projection_id") or self._make_node_id(npc_id)
        importance = float(memory.get("importance", 0.9))
        memory_type = memory.get("type", "event")
        memory_time = memory.get("created_at_game_time", game_time)
        memory_day = int(memory.get("created_day", self._parse_game_day(memory_time) or self._parse_game_day(game_time)))
        created_edges = 0
        self.db.insert_node({"id": memory_id, "subject_id": npc_id, "created_at_game_time": memory_time})
        lance_node = self._make_lance_node(
            memory_id,
            memory_type,
            memory["value"],
            importance=importance,
            game_day=memory_day,
        )
        lance_node["npc_id"] = npc_id
        lance_batch.append(lance_node)

        involved_ab, involved_ba = resolve_edge_clarity(
            "involved",
            importance,
            node_a_type=memory_type,
            node_b_type="self",
        )
        self.db.insert_edge({
            "id": f"edge_seed_self_{npc_id}_{memory_id}",
            "node_a": memory_id,
            "node_b": self_id,
            "type": "involved",
            "clarity_ab": involved_ab,
            "clarity_ba": involved_ba,
            "target_importance": importance,
            "created_at_game_time": memory_time,
        })
        created_edges += 1

        subject_ids = memory.get("subject_ids")
        if subject_ids is None:
            target_id = memory.get("target_id")
            subject_ids = [target_id] if target_id else []
        target_ids = dict.fromkeys(subject_ids)
        for target_id in target_ids:
            target_person_id = person_node_ids.get(target_id)
            if not target_person_id:
                continue
            target_ab, target_ba = resolve_edge_clarity(
                "involved",
                importance,
                node_a_type=memory_type,
                node_b_type="person",
            )
            self.db.insert_edge({
                "id": f"edge_seed_target_{npc_id}_{memory_id}_{target_id}",
                "node_a": memory_id,
                "node_b": target_person_id,
                "type": "involved",
                "clarity_ab": target_ab,
                "clarity_ba": target_ba,
                "target_importance": importance,
                "created_at_game_time": memory_time,
            })
            created_edges += 1

        if memory.get("source_fact_id"):
            scope = next(
                fact.knowledge_scope.value
                for fact in self._initial_knowledge_facts
                if fact.fact_id == memory["source_fact_id"]
            )
            self.db.insert_initial_projection({
                "projection_id": memory_id,
                "node_id": memory_id,
                "observer_id": npc_id,
                "source_fact_id": memory["source_fact_id"],
                "fact_type": memory["fact_type"],
                "knowledge_scope": scope,
                "visibility_rule": memory["visibility_rule"],
                "visibility_reason": memory["visibility_reason"],
                "source_type": memory["source_type"],
                "confidence": memory["confidence"],
                "importance": importance,
                "subject_ids": memory.get("subject_ids", []),
                "location_ids": memory.get("location_ids", []),
                "created_day": memory_day,
            })

        if memory.get("emotion"):
            emotion_id = self._make_node_id(npc_id)
            self.db.insert_node({"id": emotion_id, "subject_id": npc_id, "created_at_game_time": memory_time})
            lance_batch.append(
                self._make_lance_node(
                    emotion_id,
                    "emotion",
                    memory["emotion"],
                    importance=importance,
                    game_day=memory_day,
                )
            )

            felt_ab, felt_ba = resolve_edge_clarity(
                "felt",
                importance,
                node_a_type=memory_type,
                node_b_type="emotion",
            )
            self.db.insert_edge({
                "id": f"edge_felt_{npc_id}_{memory_id}",
                "node_a": memory_id,
                "node_b": emotion_id,
                "type": "felt",
                "clarity_ab": felt_ab,
                "clarity_ba": felt_ba,
                "target_importance": importance,
                "created_at_game_time": memory_time,
            })
            created_edges += 1

        return created_edges

    def _init_player_memories(self):
        """写入玩家初始童年记忆"""
        memories = [
            {
                "about": "sakura",
                "content": "鹿岛樱是隔壁花店的姐姐。小时候我在她家门口放过一株牵牛花，她笑得很开心。",
                "importance": 0.5,
            },
            {
                "about": "chihaya",
                "content": "千早是我小时候的玩伴，经常一起在商店街跑来跑去。她是孩子王。",
                "importance": 0.4,
            },
            {
                "about": None,
                "content": "奶奶的喫茶店以前是街上最热闹的地方。她去世后店就关了。钥匙好像在花店樱姐那里。",
                "importance": 0.6,
            },
            {
                "about": "kazuha",
                "content": "和叶的爷爷以前开旧书店。我喜欢去那里看漫画，但不知道现在书店还在不在。",
                "importance": 0.2,
            },
        ]
        for mem in memories:
            self.db.execute(
                """INSERT INTO player_memories (id, type, about_npc, content, source, game_time, importance)
                   VALUES (?, 'childhood', ?, ?, 'childhood', 'Day 0', ?)""",
                (f"pmem_{uuid.uuid4().hex[:8]}",
                 mem["about"], mem["content"], mem["importance"]),
            )

    # ═══════════════════════════════════════════
    # 状态读取与统一更新
    # ═══════════════════════════════════════════

    def get_state(self, npc_id: str) -> dict | None:
        """读取当前 NPC 状态。"""
        return self.db.fetchone("SELECT * FROM npc_states WHERE npc_id = ?", (npc_id,))

    def get_next_day_plan_context(self, npc_id: str) -> str:
        """读取夜间生成的次日计划上下文。"""
        row = self.get_state(npc_id)
        return row.get("next_day_plan_context", "") if row else ""

    def get_impression_bundle(self, owner_id: str, target_id: str) -> dict:
        """读取“基准印象 + 白天微调”的合成结果。"""
        row = self.db.fetchone(
            "SELECT * FROM npc_impressions WHERE owner_id = ? AND target_id = ?",
            (owner_id, target_id),
        )
        if not row:
            target_name = self._get_npc_name(target_id)
            return {
                "text": f"对{target_name}目前还没有明确判断。",
                "speech_hint": "先正常、礼貌地说话。",
                "approach_bias": 0.0,
                "delta_note": "",
            }

        delta_note = row.get("delta_note", "").strip()
        text = row.get("baseline_impression", "")
        if delta_note:
            text = f"{text} 今天刚发生：{delta_note}"

        return {
            "text": text.strip(),
            "speech_hint": row.get("speech_hint", "").strip(),
            "approach_bias": round(
                _clamp(float(row.get("approach_bias", 0.0)) + float(row.get("delta_bias", 0.0)), -1.0, 1.0),
                2,
            ),
            "delta_note": delta_note,
        }

    def begin_new_day(self, npc_id: str) -> None:
        """按夜间结算结果重置为次日状态。"""
        state = self.get_state(npc_id)
        if not state:
            return

        energy = min(100.0, float(state.get("energy", 80.0)) + 60.0)
        emotion_baseline = state.get("emotion_baseline", "平静")
        sociability_baseline = float(state.get("sociability_baseline", state.get("sociability", 50.0)))

        self.db.execute(
            """UPDATE npc_states
               SET emotion = ?, emotion_delta = 0.0,
                   energy = ?, sociability = ?, sociability_delta = 0.0,
                   current_need = NULL, is_asleep = 0, updated_at = datetime('now')
               WHERE npc_id = ?""",
            (emotion_baseline, energy, sociability_baseline, npc_id),
        )

    def set_current_need(self, npc_id: str, need: str | None) -> None:
        """统一更新当前需求。"""
        self.db.execute(
            "UPDATE npc_states SET current_need = ?, updated_at = datetime('now') WHERE npc_id = ?",
            (need, npc_id),
        )

    def apply_interaction_effect(self, owner_id: str, target_id: str,
                                 summary: str, source: str = "dialogue",
                                 base_world_revision: int = 0,
                                 operation_id: str = "") -> dict | None:
        """把一次互动转成 NpcStateEffect，并只在 Python 侧写入目标印象微调。"""
        state = self.get_state(owner_id)
        if not state or not summary:
            return None

        score = self._score_interaction(summary)
        row = self.db.fetchone(
            "SELECT * FROM npc_impressions WHERE owner_id = ? AND target_id = ?",
            (owner_id, target_id),
        )
        if row is None:
            self.db.execute(
                """INSERT OR REPLACE INTO npc_impressions
                   (owner_id, target_id, baseline_impression, speech_hint, approach_bias,
                    delta_note, delta_bias, updated_game_day)
                   VALUES (?, ?, '', '', 0.0, '', 0.0, 1)""",
                (owner_id, target_id),
            )
            row = self.db.fetchone(
                "SELECT * FROM npc_impressions WHERE owner_id = ? AND target_id = ?",
                (owner_id, target_id),
            ) or {}

        delta_bias = _clamp(float(row.get("delta_bias", 0.0)) + score * 0.45, -1.0, 1.0)
        emotion_delta = float(state.get("emotion_delta", 0.0)) + score * 8.0
        sociability_delta = float(state.get("sociability_delta", 0.0)) + score * 10.0
        energy = float(state.get("energy", 80.0))

        if source == "player_dialogue":
            energy = _clamp(energy - 0.6, 0.0, 100.0)
        elif source == "npc_dialogue":
            energy = _clamp(energy - 0.3, 0.0, 100.0)

        updates = self._compose_state_update(state, energy, emotion_delta, sociability_delta)
        concern = state.get("lingering_concern", "")
        if score < -0.45:
            concern = summary[:80]

        self.db.execute(
            """UPDATE npc_impressions
               SET delta_note = ?, delta_bias = ?, updated_at = datetime('now')
               WHERE owner_id = ? AND target_id = ?""",
            (summary[:120], delta_bias, owner_id, target_id),
        )
        return {
            "type": "NPC_STATE_EFFECT",
            "operation_id": operation_id or f"state_effect_{owner_id}_{source}",
            "npc_id": owner_id,
            "base_world_revision": int(base_world_revision or 0),
            "effect_type": "interaction",
            "field_deltas": {
                "energy": round(updates["energy"] - float(state.get("energy", 80.0)), 3),
                "sociability": round(updates["sociability"] - float(state.get("sociability", 50.0)), 3),
            },
            "field_values": {
                "emotion": updates["emotion"],
                "emotion_delta": round(updates["emotion_delta"], 3),
                "sociability_delta": round(updates["sociability_delta"], 3),
                "lingering_concern": concern,
            },
            "clamp_reasons": [],
            "source": source,
            "reason": summary[:120],
        }

    def nightly_refresh(self, game_day: int) -> None:
        """兼容旧调用，并委托固定玩家目标的午夜印象深模块。"""
        if self._retrieval is None:
            raise RuntimeError("nightly_refresh_requires_retrieval")
        from .player_impression_refresh import PlayerImpressionRefresher

        refresher = PlayerImpressionRefresher(self, self._retrieval, ALL_NPC_IDS)
        prepared = refresher.prepare_inputs(game_day)
        generated = refresher.generate(prepared)
        refresher.commit(generated, game_day)
        refresher.refresh_next_day_baselines(game_day)

    # ═══════════════════════════════════════════
    # 夜间生成：印象 / 计划摘要 / 次日基准状态
    # ═══════════════════════════════════════════

    def _rebuild_impressions_for_npc(self, npc_id: str, profile: dict,
                                     game_day: int,
                                     target_query_vectors: dict[str, list[float]]) -> None:
        """用图和短期记忆重建 NPC 对熟人的基准印象。"""
        owner_name = profile.get("name", npc_id)
        state = self.get_state(npc_id) or {}
        tasks: list[dict] = []

        for target_id in TARGET_IDS:
            if target_id == npc_id:
                continue

            recent_memories = self._recent_target_memories(npc_id, target_id, game_day)
            current = self.get_impression_bundle(npc_id, target_id)
            target_name = self._get_npc_name(target_id)
            tasks.append({
                "order": len(tasks),
                "npc_id": npc_id,
                "target_id": target_id,
                "target_name": target_name,
                "recent_memories": recent_memories,
                "query_vector": target_query_vectors.get(target_id),
                "game_day": game_day,
                "previous": current["text"],
            })

        results = self._generate_impressions_parallel(
            owner_name=owner_name,
            personality=profile.get("personality", ""),
            lingering_concern=state.get("lingering_concern", ""),
            tasks=tasks,
        )

        for item in results:
            baseline = item["baseline"]
            self.db.execute(
                """INSERT INTO npc_impressions
                   (owner_id, target_id, baseline_impression, speech_hint, approach_bias,
                    delta_note, delta_bias, updated_game_day, updated_at)
                   VALUES (?, ?, ?, ?, ?, '', 0.0, ?, datetime('now'))
                   ON CONFLICT(owner_id, target_id) DO UPDATE SET
                       baseline_impression = excluded.baseline_impression,
                       speech_hint = excluded.speech_hint,
                       approach_bias = excluded.approach_bias,
                       delta_note = '',
                       delta_bias = 0.0,
                       updated_game_day = excluded.updated_game_day,
                       updated_at = datetime('now')""",
                (
                    npc_id,
                    item["target_id"],
                    baseline["baseline_impression"],
                    baseline["speech_hint"],
                    baseline["approach_bias"],
                    game_day,
                ),
            )

        plan_context = self._build_plan_context(npc_id, game_day)
        self.db.execute(
            "UPDATE npc_states SET next_day_plan_context = ?, updated_at = datetime('now') WHERE npc_id = ?",
            (plan_context, npc_id),
        )

    def _build_target_query_vectors(self) -> dict[str, list[float]]:
        """为夜间图检索预先生成熟人查询向量，避免重复编码人物名。"""
        try:
            from ..memory.embedding import encode_batch

            target_ids = list(TARGET_IDS)
            target_names = [self._get_npc_name(target_id) for target_id in target_ids]
            vecs = encode_batch(target_names)
            if vecs is None:
                return {}
            return {
                target_id: vecs[index].tolist()
                for index, target_id in enumerate(target_ids)
            }
        except Exception as e:
            logger.debug(f"夜间查询向量预生成失败: {e}")
            return {}

    def _generate_impressions_parallel(self, owner_name: str, personality: str,
                                       lingering_concern: str,
                                       tasks: list[dict]) -> list[dict]:
        """并发生成一组熟人基准印象，再按原顺序返回。"""
        if not tasks:
            return []

        if len(tasks) == 1:
            return [self._run_impression_task(owner_name, personality, lingering_concern, tasks[0])]

        max_workers = min(NIGHTLY_IMPRESSION_MAX_WORKERS, len(tasks))
        results: list[dict] = []

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="nightly-impression") as pool:
            futures = {
                pool.submit(
                    self._run_impression_task,
                    owner_name,
                    personality,
                    lingering_concern,
                    task,
                ): task
                for task in tasks
            }
            for future in as_completed(futures):
                task = futures[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.warning(f"并发印象生成失败 ({owner_name}->{task['target_name']}): {e}")
                    results.append({
                        **task,
                        "baseline": self._fallback_impression(
                            task["target_name"],
                            task["recent_memories"],
                            task.get("graph_memories", "（图记忆不可用）"),
                            task["previous"],
                        ),
                    })

        results.sort(key=lambda item: item["order"])
        return results

    def _run_impression_task(self, owner_name: str, personality: str,
                             lingering_concern: str, task: dict) -> dict:
        """执行单个熟人印象生成任务。"""
        graph_memories = self._graph_target_memories(
            task["npc_id"],
            task["target_id"],
            task.get("query_vector"),
            task.get("game_day", 1),
        )
        baseline = self._generate_impression(
            owner_name=owner_name,
            personality=personality,
            lingering_concern=lingering_concern,
            target_name=task["target_name"],
            recent_memories=task["recent_memories"],
            graph_memories=graph_memories,
            previous=task["previous"],
        )
        return {**task, "graph_memories": graph_memories, "baseline": baseline}

    def _refresh_baseline_state(self, npc_id: str, profile: dict) -> None:
        """根据当天互动结果刷新次日基准状态。"""
        state = self.get_state(npc_id)
        if not state:
            return

        impressions = self.db.fetchall(
            "SELECT approach_bias, delta_note, baseline_impression FROM npc_impressions WHERE owner_id = ?",
            (npc_id,),
        )
        avg_bias = sum(float(r.get("approach_bias", 0.0)) for r in impressions) / max(len(impressions), 1)
        emotion_delta = float(state.get("emotion_delta", 0.0))
        baseline_emotion = self._resolve_emotion(
            state.get("emotion_baseline", "平静"),
            emotion_delta * 0.4,
            state.get("lingering_concern", ""),
        )
        sociability_baseline = _clamp(
            float(profile.get("social_base", 50.0)) + avg_bias * 12.0 + float(state.get("sociability_delta", 0.0)) * 0.3,
            0.0,
            100.0,
        )
        concern = self._derive_lingering_concern(npc_id, state)

        self.db.execute(
            """UPDATE npc_states
               SET emotion_baseline = ?, sociability_baseline = ?, lingering_concern = ?,
                   updated_at = datetime('now')
               WHERE npc_id = ?""",
            (baseline_emotion, sociability_baseline, concern, npc_id),
        )

    # ═══════════════════════════════════════════
    # 辅助
    # ═══════════════════════════════════════════

    def _recent_target_memories(self, npc_id: str, target_id: str, game_day: int) -> str:
        """收集最近几天与目标相关的短期记忆。"""
        rows = self.db.fetchall(
            """SELECT content, participants, created_at_game_time
               FROM short_term_memories
               WHERE subject_id = ?
               ORDER BY created_at DESC
               LIMIT 16""",
            (npc_id,),
        )
        target_hits: list[str] = []
        target_name = self._get_npc_name(target_id)
        target_aliases = get_player_name_candidates() if target_id == "player" else (target_name,)
        for row in rows:
            time_str = row.get("created_at_game_time", "")
            day = self._parse_game_day(time_str)
            if game_day - day > 3:
                continue
            participants = row.get("participants") or ""
            content = row.get("content", "")
            if target_id in participants or any(alias in content for alias in target_aliases):
                target_hits.append(render_player_tokens(content[:140]))
        return "\n".join(f"- {text}" for text in target_hits[:4]) or "（最近没有特别直接的互动）"

    def _graph_target_memories(self, npc_id: str, target_id: str,
                               query_vector: list[float] | None = None,
                               game_day: int = 1) -> str:
        """夜间优先用多跳图路由取目标相关记忆，失败时回退向量搜索。"""
        if self._retrieval is not None:
            try:
                routed = self._retrieval.retrieve(
                    npc_id,
                    target_id,
                    location="nightly_reflection",
                    game_time=f"第{game_day}天 24:00",
                    mode="nightly_impression",
                )
                if routed:
                    return routed
            except Exception as e:
                logger.debug(f"夜间多跳图记忆读取失败 ({npc_id}->{target_id}): {e}")

        if not self.lancedb:
            return "（图记忆不可用）"
        try:
            if query_vector is None:
                from ..memory.embedding import encode_batch

                target_name = self._get_npc_name(target_id)
                vecs = encode_batch([target_name])
                if vecs is None:
                    return "（图记忆不可用）"
                query_vector = vecs[0].tolist()

            results = self.lancedb.search(npc_id, query_vector, top_k=5)
            snippets = []
            for row in results:
                value = row.get("value", "")
                if value:
                    snippets.append(value[:80])
            return "\n".join(f"- {text}" for text in snippets[:3]) or "（图中没有明显相关片段）"
        except Exception as e:
            logger.debug(f"图记忆片段读取失败 ({npc_id}->{target_id}): {e}")
            return "（图记忆不可用）"

    def _generate_impression(self, owner_name: str, personality: str, lingering_concern: str,
                             target_name: str, recent_memories: str,
                             graph_memories: str, previous: str) -> dict:
        """生成新的基准印象，LLM 失败时回退启发式。"""
        profile = {"personality": personality or "（未定义）"}
        prompt = self.prompt_assembler.build("nightly_impression", {
            "profile": profile, "owner_name": owner_name,
            "npc_tags": format_npc(profile), "lingering_concern": lingering_concern or "无",
            "target_name": target_name, "recent_memories": recent_memories,
            "graph_memories": graph_memories, "previous": previous or "（无）",
        })
        try:
            raw = _llm_module.llm_client.chat(
                [
                    {"role": "system", "content": "你负责把零散记忆压缩成稳定、简短的熟人印象。"},
                    {"role": "user", "content": prompt[0]["content"]},
                ],
                temperature=0.45,
            )
            data = json.loads(raw.strip().lstrip("```json").rstrip("```").strip())
            impression = str(data.get("baseline_impression", "")).strip()
            speech_hint = str(data.get("speech_hint", "")).strip()
            approach_bias = float(data.get("approach_bias", 0.0))
            return {
                "baseline_impression": impression or f"对{target_name}的感觉暂时没有明显变化。",
                "speech_hint": speech_hint or "先按平常语气交流。",
                "approach_bias": round(_clamp(approach_bias, -1.0, 1.0), 2),
                "emotion_baseline": str(data.get("emotion_baseline", "平静")).strip() or "平静",
                "lingering_concern": str(data.get("lingering_concern", "")).strip(),
            }
        except Exception as e:
            logger.debug(f"LLM 印象生成失败 ({owner_name}->{target_name}): {e}")
            return self._fallback_impression(target_name, recent_memories, graph_memories, previous)

    def _fallback_impression(self, target_name: str, recent_memories: str,
                             graph_memories: str, previous: str) -> dict:
        """没有 LLM 时的基础印象回退。"""
        text_source = f"{recent_memories}\n{graph_memories}\n{previous}"
        score = self._score_interaction(text_source)
        if score > 0.35:
            return {
                "baseline_impression": f"最近想到{target_name}时整体是偏安心和亲近的。",
                "speech_hint": "语气可以柔和、自然一些。",
                "approach_bias": 0.45,
                "emotion_baseline": "开心",
                "lingering_concern": "",
            }
        if score < -0.35:
            return {
                "baseline_impression": f"最近想到{target_name}时会有点别扭，暂时想保持距离。",
                "speech_hint": "语气收一点，先观察对方反应。",
                "approach_bias": -0.45,
                "emotion_baseline": "紧张",
                "lingering_concern": recent_memories.split("\n")[0][:60] if recent_memories else "",
            }
        return {
            "baseline_impression": f"对{target_name}还是维持平常看法，暂时没有特别大的变化。",
            "speech_hint": "先按平常语气交流。",
            "approach_bias": 0.0,
            "emotion_baseline": "平静",
            "lingering_concern": "",
        }

    def _build_plan_context(self, npc_id: str, game_day: int) -> str:
        """拼装供次日日计划读取的夜间摘要。"""
        state = self.get_state(npc_id) or {}
        memories = self.db.fetchall(
            """SELECT content, created_at_game_time
               FROM short_term_memories
               WHERE subject_id = ?
               ORDER BY created_at DESC
               LIMIT 10""",
            (npc_id,),
        )
        recent = [
            row["content"][:100]
            for row in memories
            if game_day - self._parse_game_day(row.get("created_at_game_time", "")) <= 2
        ][:3]

        impressions = self.db.fetchall(
            """SELECT target_id, baseline_impression, delta_note, approach_bias, delta_bias
               FROM npc_impressions
               WHERE owner_id = ?
               ORDER BY ABS(approach_bias + delta_bias) DESC
               LIMIT 3""",
            (npc_id,),
        )
        lines = []
        if state.get("lingering_concern"):
            lines.append(f"你心里还挂着：{state['lingering_concern']}")
        if recent:
            lines.append("最近发生：")
            lines.extend(f"- {text}" for text in recent)
        if impressions:
            lines.append("你对熟人的当前感觉：")
            for row in impressions:
                target_name = self._get_npc_name(row["target_id"])
                bias = float(row.get("approach_bias", 0.0)) + float(row.get("delta_bias", 0.0))
                mood = "更想接近" if bias > 0.25 else ("有点想回避" if bias < -0.25 else "维持平常距离")
                lines.append(f"- 对{target_name}：{row.get('baseline_impression','')[:70]}（{mood}）")
        return "\n".join(lines)[:420]

    def _derive_lingering_concern(self, npc_id: str, state: dict) -> str:
        """从现有状态和最近记忆推一个次日延续的心事。"""
        if state.get("lingering_concern"):
            return str(state["lingering_concern"])[:120]
        rows = self.db.fetchall(
            """SELECT content
               FROM short_term_memories
               WHERE subject_id = ?
               ORDER BY importance DESC, created_at DESC
               LIMIT 6""",
            (npc_id,),
        )
        for row in rows:
            content = row.get("content", "")
            if self._score_interaction(content) < -0.2:
                return content[:100]
        return ""

    def _compose_state_update(self, state: dict, energy: float,
                              emotion_delta: float, sociability_delta: float) -> dict:
        """由 baseline + delta 计算当前展示状态。"""
        emotion_delta = _clamp(emotion_delta, -12.0, 12.0)
        sociability_delta = _clamp(sociability_delta, -25.0, 25.0)
        emotion = self._resolve_emotion(
            state.get("emotion_baseline", "平静"),
            emotion_delta,
            state.get("lingering_concern", ""),
        )
        sociability = _clamp(
            float(state.get("sociability_baseline", state.get("sociability", 50.0))) + sociability_delta,
            0.0,
            100.0,
        )
        return {
            "emotion": emotion,
            "emotion_delta": round(emotion_delta, 2),
            "energy": round(energy, 2),
            "sociability": round(sociability, 2),
            "sociability_delta": round(sociability_delta, 2),
        }

    def _resolve_emotion(self, baseline: str, delta: float, concern: str) -> str:
        """把夜间基线和白天波动合成为当前情绪标签。"""
        if delta >= 4.0:
            return "开心"
        if delta <= -5.5:
            return "低落"
        if concern and delta < -1.5:
            return "紧张"
        return baseline if baseline in EMOTION_ORDER else "平静"

    @staticmethod
    def _energy_delta_for_action(action: str) -> float:
        """按行为类型估算每分钟精力变化。"""
        if action in {"sleep"}:
            return 1.0
        if action in {"rest", "eat"}:
            return 0.45
        if action in {"drink", "read", "sit"}:
            return 0.2
        if action in {"work_open", "work_close", "work_craft", "work_arrange", "work_clean"}:
            return -0.28
        if action in {"patrol", "visit", "browse", "talk", "give_item"}:
            return -0.18
        return -0.05

    @staticmethod
    def _score_interaction(text: str) -> float:
        """基于关键词的轻量情绪评分，用于白天即时波动。"""
        positive = ["开心", "笑", "温柔", "安心", "谢谢", "帮", "喜欢", "轻松", "高兴", "愿意"]
        negative = ["冷淡", "尴尬", "生气", "烦", "拒绝", "躲", "争", "不想", "紧张", "难过"]
        score = 0.0
        for word in positive:
            if word in text:
                score += 0.18
        for word in negative:
            if word in text:
                score -= 0.2
        return _clamp(score, -1.0, 1.0)

    @staticmethod
    def _parse_game_day(time_str: str) -> int:
        """从“第X天 HH:MM”中取出 X。"""
        if not time_str:
            return 0
        digits = []
        for ch in time_str:
            if ch.isdigit():
                digits.append(ch)
            elif digits:
                break
        return int("".join(digits)) if digits else 0

    def _make_node_id(self, subject_id: str) -> str:
        """生成节点 ID（v0.6 极简，只有 ID）"""
        return f"node_{subject_id}_{uuid.uuid4().hex[:8]}"

    def _make_lance_node(self, node_id: str, node_type: str, value: str,
                         importance: float = 0.5, game_day: int = 1) -> dict:
        """构建 LanceDB 节点数据"""
        return {
            "node_id": node_id, "vector": [],
            "type": node_type, "value": render_player_tokens(value),
            "importance": importance, "created_day": game_day,
            "archived": 0,
        }

    def _default_location(self, npc_id: str) -> str:
        locations = {
            "sakura": "flower_shop.counter",
            "chihaya": "bakery.kneading_table",
            "kazuha": "bookstore.reading_sofa",
            "tatsunosuke": "wagashi.back_workbench",
            "kujo": "police_box.desk",
        }
        return locations.get(npc_id, "street.crossroad")

    def _get_npc_name(self, npc_id: str) -> str:
        """返回 NPC 或玩家的显示名。"""
        names = {
            "player": get_player_display_name(),
            "sakura": "鹿岛樱",
            "chihaya": "千早",
            "kazuha": "和叶",
            "tatsunosuke": "龙之介",
            "kujo": "九条莲",
        }
        return names.get(npc_id, npc_id)
