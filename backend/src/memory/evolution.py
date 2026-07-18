"""
图演化引擎 v0.6 — 反思生成 + 节点融合。
similar_to 由 BGE 在检索时实时计算，不再建边。
精度转换由 LanceDB 的 clarity 衰减自然完成。
"""
import uuid
import logging

from ..database.sqlite_client import SQLiteClient
from ..dialogue import llm_client as _llm_module
from ..prompting import PromptAssembler

logger = logging.getLogger("sakurabashi.evolution")

MERGE_PROMPT = "将以下两个模糊记忆合并为一个更概括的表达:\nA: {a}\nB: {b}\n\n只输出合并后的版本（1句话）:"
MERGE_MAX_PAIRS_PER_NPC = 2
MERGE_SIMILARITY_THRESHOLD = 0.85


class EvolutionEngine:
    """夜间图演化引擎 v0.6 — 仅反思 + 融合"""

    def __init__(self, db: SQLiteClient, lancedb=None):
        self.db = db
        self.lancedb = lancedb
        self.prompt_assembler = PromptAssembler()

    def run_all_sync(self, npc_ids: list[str], game_time: str):
        """串行执行所有 NPC 演化"""
        for npc_id in npc_ids:
            try:
                self._merging(npc_id, game_time)
            except Exception as e:
                logger.error(f"演化失败 ({npc_id}): {e}")

    # ════════════════════════════════
    # 节点融合
    # ════════════════════════════════

    def _merging(self, npc_id: str, game_time: str = ""):
        """BGE 相似度足够高时融合节点，并继承旧节点邻边。"""
        if not self.lancedb:
            return

        # 获取活跃节点
        node_ids = [r["id"] for r in self.db.get_nodes_by_npc(npc_id)]
        if len(node_ids) < 2:
            return

        nodes = self.lancedb.get_batch(npc_id, node_ids)
        events = [n for n in nodes if n.get("type") == "event" and not n.get("archived")]
        if len(events) < 2:
            return

        from .embedding import pairwise_similarities
        texts = [e["value"] for e in events[:15]]
        sims = pairwise_similarities(texts)
        if not sims:
            return

        count = 0
        for i, j, sim in sims:
            if sim < MERGE_SIMILARITY_THRESHOLD or count >= MERGE_MAX_PAIRS_PER_NPC:
                break
            a, b = events[i], events[j]

            try:
                source_ids = [a["node_id"], b["node_id"]]
                merged_id = f"node_{npc_id}_merged_{uuid.uuid4().hex[:8]}"
                inherited_edges = self._build_inherited_edges(npc_id, merged_id, source_ids)
                if not inherited_edges:
                    logger.debug("融合跳过: %s/%s 无可继承邻边", a["node_id"], b["node_id"])
                    continue

                prompt = self.prompt_assembler.build("memory_merge", {"a": a["value"], "b": b["value"]})
                raw = _llm_module.llm_client.chat(
                    prompt,
                    temperature=0.5)
                merged_value = raw.strip().strip('"')

                avg_imp = (a.get("importance", 0.5) + b.get("importance", 0.5)) / 2
                merged_created_day = self._merged_created_day(a, b)

                self.db.insert_node({
                    "id": merged_id, "subject_id": npc_id,
                    "created_at_game_time": game_time or "auto",
                })

                # LanceDB: 融合节点
                from .embedding import encode_batch
                vecs = encode_batch([merged_value])
                self.lancedb.upsert_node(npc_id, {
                    "node_id": merged_id,
                    "vector": vecs[0].tolist() if vecs is not None else [0]*512,
                    "type": "event", "value": merged_value,
                    "importance": round(avg_imp, 2),
                    "created_day": merged_created_day, "archived": 0,
                })

                for edge in inherited_edges:
                    self.db.insert_edge(edge)
                for source in (a, b):
                    self.db.insert_merge_source({
                        "merged_node_id": merged_id,
                        "source_node_id": source["node_id"],
                        "npc_id": npc_id,
                        "source_type": source.get("type", ""),
                        "source_value": source.get("value", ""),
                        "similarity": sim,
                        "created_at_game_time": game_time or "auto",
                    })

                # 旧节点从图层退场，向量层保留 archived，供强制回忆追溯。
                self.db.delete_edges_touching_node_ids(source_ids)
                for node_id in source_ids:
                    self.db.delete_node(node_id)
                    self.lancedb.set_archived(npc_id, node_id, True)

                degree = self.db.get_node_degree(merged_id)
                logger.info(
                    "[融合] npc=%s merged=%s sources=%s inherited_edges=%s degree=%s sim=%.3f",
                    npc_id,
                    merged_id,
                    source_ids,
                    len(inherited_edges),
                    degree,
                    sim,
                )

                count += 1
            except Exception as e:
                logger.debug(f"融合跳过: {e}")

        if count:
            logger.info(f"融合 ({npc_id}): {count} 对")

    def _build_inherited_edges(self, npc_id: str, merged_id: str,
                               source_ids: list[str]) -> list[dict]:
        """把旧节点邻边转换为融合节点邻边，保留双向 clarity 语义。"""
        source_set = set(source_ids)
        inherited_by_key: dict[tuple[str, str], dict] = {}
        for edge in self.db.get_edges_touching_node_ids(source_ids):
            node_a = edge.get("node_a", "")
            node_b = edge.get("node_b", "")
            if node_a in source_set and node_b in source_set:
                continue

            if node_a in source_set:
                neighbor_id = node_b
                merged_to_neighbor = self._float_field(edge, "clarity_ab", 0.7)
                neighbor_to_merged = self._float_field(edge, "clarity_ba", 0.7)
            elif node_b in source_set:
                neighbor_id = node_a
                merged_to_neighbor = self._float_field(edge, "clarity_ba", 0.7)
                neighbor_to_merged = self._float_field(edge, "clarity_ab", 0.7)
            else:
                continue

            if not neighbor_id or neighbor_id == merged_id or neighbor_id in source_set:
                continue

            edge_type = edge.get("type", "associated_with")
            key = (neighbor_id, edge_type)
            existing = inherited_by_key.get(key)
            if existing is None:
                inherited_by_key[key] = {
                    "id": f"edge_merge_{npc_id}_{uuid.uuid4().hex[:8]}",
                    "node_a": merged_id,
                    "node_b": neighbor_id,
                    "type": edge_type,
                    "clarity_ab": merged_to_neighbor,
                    "clarity_ba": neighbor_to_merged,
                    "target_importance": self._float_field(edge, "target_importance", 0.5),
                    "created_at_game_time": edge.get("created_at_game_time", ""),
                }
                continue

            existing["clarity_ab"] = max(existing["clarity_ab"], merged_to_neighbor)
            existing["clarity_ba"] = max(existing["clarity_ba"], neighbor_to_merged)
            existing["target_importance"] = max(
                existing["target_importance"],
                self._float_field(edge, "target_importance", 0.5),
            )
            if not existing.get("created_at_game_time") and edge.get("created_at_game_time"):
                existing["created_at_game_time"] = edge["created_at_game_time"]

        return list(inherited_by_key.values())

    @staticmethod
    def _float_field(row: dict, key: str, default: float) -> float:
        """读取允许为 0 的浮点字段，避免用 `or default` 覆盖合法零值。"""
        value = row.get(key)
        if value is None:
            return default
        return float(value)

    @staticmethod
    def _node_created_day(node: dict) -> int:
        """读取允许为 Day 0 的节点日期字段。"""
        value = node.get("created_day")
        if value is None:
            return 1
        return int(value)

    def _merged_created_day(self, a: dict, b: dict) -> int:
        """融合节点使用来源中较新的日期，避免把近期概括标成过旧记忆。"""
        return max(self._node_created_day(a), self._node_created_day(b))
