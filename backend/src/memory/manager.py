"""
记忆图管理器 v0.6 — 边 clarity 衰减 + LanceDB 数据持久化。
图 = 联想层(边清晰度)  |  LanceDB = 数据层(节点内容)
"""
from collections import Counter
import json
import uuid
import logging
import os

from ..database.sqlite_client import SQLiteClient
from ..dialogue import llm_client as _llm_module
from .edge_semantics import resolve_edge_clarity
from .embedding import encode_batch
from .embedding import pairwise_similarities as _bge_similarities
from ..prompting import PromptAssembler

logger = logging.getLogger("sakurabashi.memory")


def _memory_trace_enabled() -> bool:
    return os.getenv("SAKURA_MEMORY_TRACE", "").strip().lower() in {"1", "true", "yes", "on"}


EMOTION_KEYWORDS = {
    "开心": ["开心", "高兴", "笑", "轻松", "安心", "温柔", "愉快"],
    "紧张": ["紧张", "担心", "不安", "慌", "忐忑"],
    "低落": ["难过", "失落", "沮丧", "委屈", "疲惫", "烦", "生气"],
    "平静": ["平静", "安静", "平和", "稳定"],
}

# ── 衰减常量 ──
DECAY_PEAK = 0.343          # importance=0.5 时的日衰减率 (~7天遗忘)
CLARITY_DELETE_THRESHOLD = 0.05  # clarity 低于此值删边
CLARITY_RECOVERY_FACTOR = 0.1    # 恢复系数

# ── 结构边（不衰减）──
STRUCTURAL_EDGE_TYPES = {"involved", "sequenced", "located_at", "contains"}

# ── 写入过滤 ──
MIN_IMPORTANCE = 0.3

# ── 提取 Prompt ──
EXTRACTION_PROMPT = """从以下事件原文中提取记忆节点和边。

## 节点类型
- person: 人物, event: 事件, emotion: 情绪
- time_exact: 精确时间, place_exact: 精确地点
- sensory: 感官, item: 物品, quote: 话语

## 边类型
- involved: 事件→人物, happened_at: 事件→时间
- located_at: 事件→地点, felt: 事件→情绪
- mentioned: 提到话语

## importance (0.1-1.0)
- 0.1-0.3: 日常寒暄(会被丢弃)
- 0.4-0.6: 有情感互动
- 0.7-0.9: 重要交流
- 1.0: 核心记忆

## 规则
1. 人物节点不重复
2. importance<{min_imp} 的事件丢弃, 不要创建
3. 事件 value 用第一人称简述
4. 输出纯 JSON:
{{"nodes":[{{"id":"n1","type":"event","value":"简述","importance":0.7}}],"edges":[{{"from":"n1","to":"n2","type":"happened_at"}}]}}

## 事件原文
{events}

## NPC: {name} / 时间: {time}
## 当天活跃的人物节点（复用）: {persons}
## 当天活跃的其他节点（可引用建边）: {nodes}

只输出 JSON。"""


class MemoryManager:
    """记忆图管理器 v0.6"""

    def __init__(self, db: SQLiteClient, lancedb=None):
        self.db = db
        self.lancedb = lancedb  # LanceDBClient, 可能为 None
        self.prompt_assembler = PromptAssembler()

    # ═══════════════════════════════════════════
    # 边衰减（二次U型）
    # ═══════════════════════════════════════════

    @staticmethod
    def decay_rate(importance: float) -> float:
        """二次 U 型衰减率。importance=0.5 最快。"""
        if importance >= 1.0:
            return 0.0
        d = abs(importance - 0.5)
        return DECAY_PEAK * (1.0 - (2.0 * d) ** 2)

    def clarity_decay_edges(self, npc_id: str) -> tuple[int, int]:
        """衰减 NPC 所有联想边。返回 (衰减边数, 删除边数)。"""
        edges = self.db.get_all_edges_for_decay(npc_id)
        decayed = 0
        deleted = 0

        for e in edges:
            imp = e["target_importance"]
            rate = self.decay_rate(imp)
            if rate <= 0:
                continue

            new_ab = e["clarity_ab"] * (1.0 - rate)
            new_ba = e["clarity_ba"] * (1.0 - rate)

            if new_ab < CLARITY_DELETE_THRESHOLD and new_ba < CLARITY_DELETE_THRESHOLD:
                self.db.delete_edge(e["id"])
                deleted += 1
            else:
                self.db.decay_edge_clarity(e["id"], max(0.0, new_ab), max(0.0, new_ba))
                decayed += 1

        if decayed or deleted:
            logger.info(f"边衰减 ({npc_id}): {decayed} 衰减, {deleted} 删除")
        return decayed, deleted

    def cleanup_orphan_nodes(self, npc_id: str) -> int:
        """清理孤立节点：从 SQLite 删除，LanceDB 标记 archived=1。"""
        orphans = self.db.get_orphan_nodes(npc_id)
        for nid in orphans:
            self.db.delete_node(nid)
            if self.lancedb:
                self.lancedb.set_archived(npc_id, nid, archived=True)
        if orphans:
            logger.info(f"孤点清理 ({npc_id}): {len(orphans)} 归档")
        return len(orphans)

    # ═══════════════════════════════════════════
    # 清晰度恢复
    # ═══════════════════════════════════════════

    def recover_clarity(self, edge_id: str, direction: str,
                        target_importance: float) -> None:
        """边被遍历时微涨清晰度。"""
        edge = self.db.fetchone(
            "SELECT clarity_ab, clarity_ba FROM memory_edges WHERE id = ?",
            (edge_id,))
        if not edge:
            return

        if direction == "ab":
            old = edge["clarity_ab"]
            boost = target_importance * CLARITY_RECOVERY_FACTOR * (1.0 - old)
            new_val = min(old + boost, min(target_importance * 1.5, 0.95))
            self.db.execute(
                "UPDATE memory_edges SET clarity_ab = ?, last_traversed_ab = datetime('now') WHERE id = ?",
                (round(new_val, 4), edge_id))
        else:
            old = edge["clarity_ba"]
            boost = target_importance * CLARITY_RECOVERY_FACTOR * (1.0 - old)
            new_val = min(old + boost, min(target_importance * 1.5, 0.95))
            self.db.execute(
                "UPDATE memory_edges SET clarity_ba = ?, last_traversed_ba = datetime('now') WHERE id = ?",
                (round(new_val, 4), edge_id))

        self.db.mark_edge_traversed(edge_id, direction)

    # ═══════════════════════════════════════════
    # 提取: 短期记忆 → 图节点(LanceDB) + 边(SQLite)
    # ═══════════════════════════════════════════

    def extract_and_ingest(self, npc_id: str, npc_name: str, event_text: str,
                           game_time: str = "", game_day: int = 1) -> dict:
        """LLM 提取事件并返回节点、边和非法输出的结构化计数。"""
        # 截断
        max_chars = 1500
        if len(event_text) > max_chars:
            event_text = event_text[:max_chars] + "\n..."

        # 当天活跃的已有节点（被 traversal 过的边所连接），传给 LLM 复用
        active_persons, active_nodes = self._get_today_active_nodes(npc_id)
        persons_str = ", ".join(f"{pid}={name}" for pid, name in active_persons) if active_persons else "无"
        nodes_str = ", ".join(f"{nid}: {val[:30]}" for nid, val in active_nodes[:8]) if active_nodes else "无"

        prompt = self.prompt_assembler.build("memory_extract", {
            "min_imp": MIN_IMPORTANCE, "events": event_text,
            "name": npc_name, "time": game_time, "persons": persons_str, "nodes": nodes_str,
        })

        try:
            raw = _llm_module.llm_client.chat(
                prompt,
                temperature=0.3)
            data = self._parse_json(raw)
            if not isinstance(data, dict) or "nodes" not in data:
                logger.warning(f"提取无效 ({npc_id}): {raw[:100]}")
                return {"success": False, "written_nodes": 0, "written_edges": 0, "invalid_nodes": 0, "invalid_edges": 0, "failure_reason": "invalid_llm_payload"}
            if _memory_trace_enabled():
                node_counts = Counter(node.get("type", "event") for node in data.get("nodes", []))
                logger.info(
                    "[记忆诊断] 提取原始 npc=%s raw_nodes=%s raw_edges=%s node_types=%s active_persons=%s active_nodes=%s",
                    npc_id,
                    len(data.get("nodes", [])),
                    len(data.get("edges", [])),
                    dict(node_counts),
                    len(active_persons),
                    len(active_nodes),
                )
        except Exception as e:
            logger.error(f"提取失败 ({npc_id}): {e}")
            return {"success": False, "written_nodes": 0, "written_edges": 0, "invalid_nodes": 0, "invalid_edges": 0, "failure_reason": str(e)}

        self._ensure_emotion_coverage(data, event_text)
        reusable_nodes, reusable_types = self._build_reusable_node_map(npc_id)
        self_node_id = reusable_nodes.get(("self", "我"))

        # 写节点
        id_map = {}
        node_type_map = {}
        lance_batch = []
        lance_texts = []
        created_node_ids = []
        written = 0
        invalid_nodes = 0
        for node in data.get("nodes", []):
            if not isinstance(node, dict) or not str(node.get("id", "")).strip():
                invalid_nodes += 1
                continue
            imp = node.get("importance", 0.5)
            if imp < MIN_IMPORTANCE:
                continue

            node_type = node.get("type", "event")
            normalized_value = self._normalize_reusable_value(node_type, node.get("value", ""))
            reusable_id = reusable_nodes.get((node_type, normalized_value))
            if reusable_id:
                id_map[node["id"]] = reusable_id
                node_type_map[reusable_id] = node_type
                continue

            real_id = f"node_{npc_id}_{uuid.uuid4().hex[:8]}"
            id_map[node["id"]] = real_id
            node_type_map[real_id] = node_type
            created_node_ids.append(real_id)

            # SQLite: 只写 ID
            self.db.insert_node({
                "id": real_id, "subject_id": npc_id,
                "created_at_game_time": game_time,
            })

            # LanceDB: 写完整数据 + 向量
            if self.lancedb:
                lance_batch.append({
                    "node_id": real_id, "vector": [],
                    "type": node_type, "value": node.get("value", ""),
                    "importance": imp, "created_day": game_day,
                    "archived": 0,
                })
                lance_texts.append(node.get("value", ""))
            written += 1

        if lance_batch and self.lancedb:
            vecs = encode_batch(lance_texts)
            if vecs is not None:
                for i, node in enumerate(lance_batch):
                    node["vector"] = vecs[i].tolist()
            else:
                for node in lance_batch:
                    node["vector"] = [0.0] * 512
            self.lancedb.upsert_nodes(npc_id, lance_batch)

        existing_type_map = {}
        referenced_existing_ids = set()
        for edge in data.get("edges", []):
            if not isinstance(edge, dict):
                continue
            from_id = edge.get("from", "")
            to_id = edge.get("to", "")
            if from_id.startswith("node_") and from_id not in id_map:
                referenced_existing_ids.add(from_id)
            if to_id.startswith("node_") and to_id not in id_map:
                referenced_existing_ids.add(to_id)

        existing_type_map = dict(reusable_types)
        if self.lancedb and referenced_existing_ids:
            try:
                batch = self.lancedb.get_batch(npc_id, list(referenced_existing_ids))
                existing_type_map.update({
                    row["node_id"]: row.get("type", "")
                    for row in batch
                    if row.get("node_id")
                })
            except Exception as e:
                logger.debug(f"已有节点类型读取失败 ({npc_id}): {e}")

        # 写边（from/to 可以是新节点 id_map[临时ID] 或已有节点 ID）
        edge_count = 0
        invalid_edges = 0
        edge_samples = []
        connected_nodes = set()
        for edge in data.get("edges", []):
            # id_map 映射临时ID→真实ID；不在 map 中且以 "node_" 开头则为已有节点引用
            if not isinstance(edge, dict):
                invalid_edges += 1
                continue
            from_id, to_id = self._resolve_extracted_edge_ids(edge, id_map, existing_type_map)
            if not from_id or not to_id:
                invalid_edges += 1
                continue
            etype = edge.get("type", "associated_with")
            imp = self._get_imp(npc_id, to_id)
            node_a_type = node_type_map.get(from_id) or existing_type_map.get(from_id, "")
            node_b_type = node_type_map.get(to_id) or existing_type_map.get(to_id, "")
            clarity_ab, clarity_ba = resolve_edge_clarity(etype, imp, node_a_type, node_b_type)

            self.db.insert_edge({
                "id": f"edge_{npc_id}_{uuid.uuid4().hex[:8]}",
                "node_a": from_id, "node_b": to_id,
                "type": etype,
                "clarity_ab": clarity_ab,
                "clarity_ba": clarity_ba,
                "target_importance": imp,
                "created_at_game_time": game_time,
            })
            connected_nodes.add(from_id)
            connected_nodes.add(to_id)
            if len(edge_samples) < 8:
                edge_samples.append({
                    "type": etype,
                    "from_type": node_a_type or "?",
                    "to_type": node_b_type or "?",
                    "clarity_ab": round(clarity_ab, 3),
                    "clarity_ba": round(clarity_ba, 3),
                    "from_id": from_id,
                    "to_id": to_id,
                })
            edge_count += 1

        fallback_edges = 0
        if self_node_id:
            for node in data.get("nodes", []):
                real_id = id_map.get(node.get("id"))
                if not real_id or real_id not in created_node_ids:
                    continue
                if node.get("type") != "event" or real_id in connected_nodes:
                    continue
                imp = self._get_imp(npc_id, real_id)
                clarity_ab, clarity_ba = resolve_edge_clarity("involved", imp, "event", "self")
                self.db.insert_edge({
                    "id": f"edge_{npc_id}_{uuid.uuid4().hex[:8]}",
                    "node_a": real_id,
                    "node_b": self_node_id,
                    "type": "involved",
                    "clarity_ab": clarity_ab,
                    "clarity_ba": clarity_ba,
                    "target_importance": imp,
                    "created_at_game_time": game_time,
                })
                connected_nodes.add(real_id)
                edge_count += 1
                fallback_edges += 1

        weak_nodes = [nid for nid in created_node_ids if self.db.get_node_degree(nid) <= 1]

        if written:
            logger.info(f"提取 ({npc_id}): {written} nodes + {edge_count} edges")
            if _memory_trace_enabled():
                logger.info(
                    "[记忆诊断] 入图完成 npc=%s written_nodes=%s written_edges=%s fallback_edges=%s weak_nodes=%s edge_samples=%s",
                    npc_id,
                    written,
                    edge_count,
                    fallback_edges,
                    weak_nodes[:8],
                    edge_samples,
                )
        return {
            "success": True,
            "written_nodes": written,
            "written_edges": edge_count,
            "invalid_nodes": invalid_nodes,
            "invalid_edges": invalid_edges,
            "failure_reason": "",
        }

    @staticmethod
    def _resolve_extracted_edge_ids(edge: dict, id_map: dict, existing_type_map: dict) -> tuple[str | None, str | None]:
        """解析提取边端点，拒绝缺字段和未知临时或持久节点 ID。"""
        raw_from = str(edge.get("from", ""))
        raw_to = str(edge.get("to", ""))
        from_id = id_map.get(raw_from) or (raw_from if raw_from.startswith("node_") and raw_from in existing_type_map else None)
        to_id = id_map.get(raw_to) or (raw_to if raw_to.startswith("node_") and raw_to in existing_type_map else None)
        return from_id, to_id

    @staticmethod
    def _normalize_reusable_value(node_type: str, value: str) -> str:
        """标准化可复用节点的 value。"""
        normalized = str(value or "").strip()
        if node_type in {"person", "emotion", "self"}:
            return normalized
        return normalized

    def _build_reusable_node_map(self, npc_id: str) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
        """构建本 NPC 现有的可复用节点映射。"""
        reusable = {}
        type_map = {}
        if not self.lancedb or not hasattr(self.lancedb, "get_batch"):
            return reusable, type_map

        node_ids = [row["id"] for row in self.db.get_nodes_by_npc(npc_id)]
        if not node_ids:
            return reusable, type_map

        try:
            batch = self.lancedb.get_batch(npc_id, node_ids)
        except Exception as e:
            logger.debug(f"可复用节点读取失败 ({npc_id}): {e}")
            return reusable, type_map

        for row in batch:
            node_id = row.get("node_id")
            node_type = row.get("type", "")
            value = self._normalize_reusable_value(node_type, row.get("value", ""))
            if not node_id or not value:
                continue
            type_map[node_id] = node_type
            if node_type == "self" and value == "我":
                reusable[(node_type, value)] = node_id
            elif node_type == "person":
                reusable[(node_type, value)] = node_id
            elif node_type == "emotion":
                reusable[(node_type, value)] = node_id
        return reusable, type_map

    def _ensure_emotion_coverage(self, data: dict, event_text: str) -> None:
        """如果事件里有明显情绪词但未抽到 felt，补一条基础情绪边。"""
        nodes = data.setdefault("nodes", [])
        edges = data.setdefault("edges", [])
        emotion_ids = {
            str(node.get("value", "")).strip(): node["id"]
            for node in nodes
            if node.get("type") == "emotion" and node.get("id")
        }
        felt_sources = {
            edge.get("from")
            for edge in edges
            if edge.get("type") == "felt"
        }

        auto_index = 1
        for node in list(nodes):
            if node.get("type") != "event" or node.get("id") in felt_sources:
                continue
            emotion = self._infer_emotion_label(f"{node.get('value', '')}\n{event_text}")
            if not emotion:
                continue

            emotion_id = emotion_ids.get(emotion)
            if not emotion_id:
                emotion_id = f"auto_emotion_{auto_index}"
                auto_index += 1
                nodes.append({
                    "id": emotion_id,
                    "type": "emotion",
                    "value": emotion,
                    "importance": min(max(float(node.get("importance", 0.5)) * 0.85, 0.4), 0.75),
                })
                emotion_ids[emotion] = emotion_id

            if not any(
                edge.get("type") == "felt" and edge.get("from") == node.get("id") and edge.get("to") == emotion_id
                for edge in edges
            ):
                edges.append({
                    "from": node.get("id"),
                    "to": emotion_id,
                    "type": "felt",
                })

    @staticmethod
    def _infer_emotion_label(text: str) -> str | None:
        """从文本里推一个基础情绪标签。"""
        for emotion, keywords in EMOTION_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return emotion
        return None

    def _get_today_active_nodes(self, npc_id: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        """获取今天被 traversal 激活的节点（不查全部，只查活跃的）。
        返回 (person_nodes, other_nodes)，每个元素是 (node_id, value)。
        """
        # 人物节点：总是返回（数量少，≤6个）
        person_rows = self.db.fetchall(
            """SELECT n.id FROM memory_nodes n
               WHERE n.subject_id = ?""", (npc_id,))
        person_ids = [r["id"] for r in (person_rows or [])]

        persons = []
        others = []
        if self.lancedb and person_ids:
            batch = self.lancedb.get_batch(npc_id, person_ids)
            for b in batch:
                if b.get("type") == "person":
                    persons.append((b["node_id"], b.get("value", "?")))

        # 今天被 traversal 过的边所连接的非 person 节点（最多 10 个）
        today = self.clock.time_str()[:6] if hasattr(self, 'clock') else ""  # "第1天"
        active_edges = self.db.fetchall(
            """SELECT DISTINCT e.node_a, e.node_b FROM memory_edges e
               WHERE (e.last_traversed_ab LIKE ? OR e.last_traversed_ba LIKE ?)
               AND (e.node_a IN (SELECT id FROM memory_nodes WHERE subject_id=?)
                OR e.node_b IN (SELECT id FROM memory_nodes WHERE subject_id=?))
               LIMIT 10""",
            (f"%{today}%", f"%{today}%", npc_id, npc_id))
        active_ids = set()
        for e in (active_edges or []):
            active_ids.add(e["node_a"])
            active_ids.add(e["node_b"])
        active_ids -= set(pid for pid, _ in persons)  # 去重人物节点

        if self.lancedb and active_ids:
            batch = self.lancedb.get_batch(npc_id, list(active_ids)[:10])
            for b in batch:
                if b.get("type") != "person":
                    others.append((b["node_id"], b.get("value", "?")[:40]))

        return persons, others

    def _get_imp(self, npc_id: str, node_id: str) -> float:
        if self.lancedb:
            return self.lancedb.get_importance(npc_id, node_id)
        return 0.5

    # ═══════════════════════════════════════════
    # JSON 解析（含 LLM 错误修复）
    # ═══════════════════════════════════════════

    def _parse_json(self, raw: str) -> dict:
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:])
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # 修复裸换行
        fixed = []
        in_string, escaped = False, False
        for ch in raw:
            if escaped:
                fixed.append(ch); escaped = False; continue
            if ch == '\\':
                fixed.append(ch); escaped = True; continue
            if ch == '"':
                in_string = not in_string
            if in_string and ch in ('\n', '\r'):
                fixed.append(' ')
            else:
                fixed.append(ch)
        fixed_str = ''.join(fixed)
        try:
            return json.loads(fixed_str)
        except json.JSONDecodeError:
            pass
        # token截断修复
        last_close = fixed_str.rfind("}")
        if last_close >= 0:
            truncated = fixed_str[:last_close+1]
        else:
            return {}
        open_b = truncated.count("{") - truncated.count("}")
        open_a = truncated.count("[") - truncated.count("]")
        truncated += "]" * max(0, open_a) + "}" * max(0, open_b)
        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            pass
        logger.warning(f"JSON 解析失败: {raw[:200]}")
        return {}
