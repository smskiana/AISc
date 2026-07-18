"""
LanceDB 向量数据库客户端 — BGE 语义搜索 + 节点持久化。
v0.6: 节点数据层，永久保留。
"""
import lancedb
import pyarrow as pa
import logging
from pathlib import Path

logger = logging.getLogger("sakurabashi.lancedb")

# LanceDB 表 schema
VECTOR_DIM = 512  # BGE-small


class LanceDBClient:
    """LanceDB 向量存储客户端"""

    def __init__(self, db_path: str, npc_ids: list[str]):
        self.db_path = db_path
        self.npc_ids = npc_ids
        Path(db_path).mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        """确保每个 NPC 的表存在（首次写入自动创建）"""
        pass

    def _table_name(self, npc_id: str) -> str:
        return f"vectors_{npc_id}"

    def _load_rows(self, table_name: str) -> list[dict]:
        """读取表内全部行，供小规模合并写入使用。"""
        if table_name not in self.db.table_names():
            return []
        try:
            tbl = self.db.open_table(table_name)
            return tbl.to_lance().to_table().to_pylist()
        except Exception as e:
            logger.warning(f"LanceDB 读取失败 ({table_name}): {e}")
            return []

    def _write_rows(self, table_name: str, rows: list[dict]) -> None:
        """将合并后的整表数据回写到 LanceDB。"""
        table = pa.table({
            "node_id": [r["node_id"] for r in rows],
            "vector": [r["vector"] for r in rows],
            "type": [r.get("type", "event") for r in rows],
            "value": [r.get("value", "") for r in rows],
            "importance": [r.get("importance", 0.5) for r in rows],
            "created_day": [r.get("created_day", 1) for r in rows],
            "archived": [r.get("archived", 0) for r in rows],
        })
        self.db.create_table(table_name, table, mode="overwrite")

    def clear_all(self) -> None:
        """清空全部 LanceDB 表，供冷启动重置整套长期记忆使用。"""
        for table_name in list(self.db.table_names()):
            try:
                self.db.drop_table(table_name)
            except Exception as e:
                logger.warning(f"LanceDB 清表失败 ({table_name}): {e}")

    # ═══════════════════════════════════════════
    # 写入
    # ═══════════════════════════════════════════

    def upsert_nodes(self, npc_id: str, nodes: list[dict]) -> None:
        """批量写入/更新节点向量。

        nodes: [{
            "node_id": str, "vector": list[float], "type": str,
            "value": str, "importance": float,
            "created_day": int, "archived": int
        }, ...]
        """
        if not nodes:
            return
        table_name = self._table_name(npc_id)
        try:
            merged: dict[str, dict] = {
                row["node_id"]: row for row in self._load_rows(table_name)
            }
            for node in nodes:
                merged[node["node_id"]] = {
                    "node_id": node["node_id"],
                    "vector": node["vector"],
                    "type": node.get("type", "event"),
                    "value": node.get("value", ""),
                    "importance": node.get("importance", 0.5),
                    "created_day": node.get("created_day", 1),
                    "archived": node.get("archived", 0),
                }
            self._write_rows(table_name, list(merged.values()))
        except Exception as e:
            logger.error(f"LanceDB 写入失败 ({npc_id}): {e}")

    def upsert_node(self, npc_id: str, node: dict) -> None:
        """写入单个节点。如果表不存在则创建，否则追加后去重。"""
        try:
            self.upsert_nodes(npc_id, [node])
        except Exception as e:
            logger.error(f"LanceDB 单节点写入失败 ({npc_id}): {e}")

    # ═══════════════════════════════════════════
    # 搜索
    # ═══════════════════════════════════════════

    @staticmethod
    def normalized_similarity(distance: object) -> float:
        """将归一化 BGE 向量的 LanceDB 默认平方 L2 距离转换为 0..1 相似度。"""
        try:
            value = float(distance)
        except (TypeError, ValueError):
            return 0.0
        # encode_batch 使用 normalize_embeddings=True；平方 L2 的理论范围为 0..4。
        return max(0.0, min(1.0, 1.0 - value / 4.0))

    def search(self, npc_id: str, query_vector: list[float],
               top_k: int = 10, include_archived: bool = False) -> list[dict]:
        """向量 ANN 搜索，返回 top_k 条最相似节点。

        Args:
            include_archived: True=强制回忆时搜全部，False=日常只搜活跃节点
        """
        table_name = self._table_name(npc_id)
        if table_name not in self.db.table_names():
            return []
        try:
            tbl = self.db.open_table(table_name)
            q = tbl.search(query_vector).limit(top_k)
            if not include_archived:
                q = q.where("archived = 0", prefilter=True)
            rows = q.to_list()
            for row in rows:
                row["similarity"] = self.normalized_similarity(row.get("_distance"))
            return rows
        except Exception as e:
            logger.warning(f"LanceDB 搜索失败 ({npc_id}): {e}")
            return []

    def get_batch(self, npc_id: str, node_ids: list[str]) -> list[dict]:
        """按 node_id 列表批量获取节点数据。"""
        if not node_ids:
            return []
        table_name = self._table_name(npc_id)
        if table_name not in self.db.table_names():
            return []
        try:
            tbl = self.db.open_table(table_name)
            # LanceDB 不支持 IN 查询，逐个查
            results = []
            all_data = tbl.to_lance().to_table()
            for nid in node_ids:
                import pyarrow.compute as pc
                mask = pc.equal(all_data.column("node_id"), nid)
                filtered = all_data.filter(mask)
                if filtered.num_rows > 0:
                    results.append({
                        "node_id": str(filtered.column("node_id")[0]),
                        "type": str(filtered.column("type")[0]),
                        "value": str(filtered.column("value")[0]),
                        "importance": float(filtered.column("importance")[0]),
                        "created_day": int(filtered.column("created_day")[0]),
                        "archived": int(filtered.column("archived")[0]),
                    })
            return results
        except Exception as e:
            logger.warning(f"LanceDB 批量查询失败: {e}")
            return []

    def set_archived(self, npc_id: str, node_id: str, archived: bool = True) -> None:
        """标记节点为已归档/恢复。"""
        table_name = self._table_name(npc_id)
        if table_name not in self.db.table_names():
            return
        try:
            tbl = self.db.open_table(table_name)
            all_data = tbl.to_lance().to_table()
            import pyarrow.compute as pc
            mask = pc.equal(all_data.column("node_id"), node_id)
            filtered = all_data.filter(mask)
            if filtered.num_rows == 0:
                return
            # 找到该行的索引
            node_ids_list = all_data.column("node_id").to_pylist()
            try:
                i = node_ids_list.index(node_id)
            except ValueError:
                return
            new_archived = list(all_data.column("archived").to_pylist())
            new_archived[i] = 1 if archived else 0
            updated = all_data.set_column(
                all_data.schema.get_field_index("archived"),
                "archived",
                pa.array(new_archived, type=pa.int32())
            )
            self.db.create_table(table_name, updated, mode="overwrite")
        except Exception as e:
            logger.warning(f"LanceDB archived 更新失败: {e}")

    def get_importance(self, npc_id: str, node_id: str) -> float:
        """获取节点 importance（用于边衰减计算）。"""
        table_name = self._table_name(npc_id)
        if table_name not in self.db.table_names():
            return 0.5
        try:
            tbl = self.db.open_table(table_name)
            all_data = tbl.to_lance().to_table()
            import pyarrow.compute as pc
            mask = pc.equal(all_data.column("node_id"), node_id)
            filtered = all_data.filter(mask)
            if filtered.num_rows > 0:
                return float(filtered.column("importance")[0])
        except Exception:
            pass
        return 0.5
