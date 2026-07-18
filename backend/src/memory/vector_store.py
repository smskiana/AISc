"""
向量存储 — SQLite 存 BGE 向量 + 暴力余弦搜索。
替代 LanceDB，零额外依赖。
"""
import json
import math
import logging

logger = logging.getLogger("sakurabashi.vectors")


class VectorStore:
    """基于 SQLite 的向量存储"""

    def __init__(self, db):
        self.db = db
        self.db.execute("CREATE TABLE IF NOT EXISTS memory_vectors (node_id TEXT PRIMARY KEY, npc_id TEXT NOT NULL, vector TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'event', value TEXT NOT NULL DEFAULT '', importance REAL NOT NULL DEFAULT 0.5, created_day INTEGER NOT NULL DEFAULT 1, archived INTEGER NOT NULL DEFAULT 0)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_vec_npc ON memory_vectors(npc_id, archived)")

    # ════════════════════════════════════
    # 写入
    # ════════════════════════════════════

    def upsert_node(self, npc_id: str, node: dict):
        """写入/更新单个节点向量"""
        vec_str = json.dumps(node.get("vector", []))
        self.db.execute(
            """INSERT OR REPLACE INTO memory_vectors
               (node_id, npc_id, vector, type, value, importance, created_day, archived)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (node["node_id"], npc_id, vec_str,
             node.get("type", "event"), node.get("value", ""),
             node.get("importance", 0.5), node.get("created_day", 1),
             node.get("archived", 0)))

    def upsert_nodes(self, npc_id: str, nodes: list[dict]):
        """批量写入"""
        for n in nodes:
            self.upsert_node(npc_id, n)

    # ════════════════════════════════════
    # 搜索
    # ════════════════════════════════════

    def search(self, npc_id: str, query_vector: list[float],
               top_k: int = 10, include_archived: bool = False) -> list[dict]:
        """暴力余弦搜索 Top-K"""
        sql = "SELECT node_id, vector, type, value, importance, created_day, archived FROM memory_vectors WHERE npc_id = ?"
        if not include_archived:
            sql += " AND archived = 0"
        rows = self.db.fetchall(sql, (npc_id,))

        if not rows:
            return []

        scored = []
        for r in rows:
            vec = json.loads(r["vector"])
            if not vec or all(v == 0 for v in vec):
                continue
            sim = _cosine(query_vector, vec)
            if sim > 0.3:  # 最低阈值
                scored.append((sim, dict(r)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:top_k]]

    def get_batch(self, npc_id: str, node_ids: list[str]) -> list[dict]:
        """批量获取节点数据"""
        if not node_ids:
            return []
        placeholders = ",".join("?" for _ in node_ids)
        return self.db.fetchall(
            f"SELECT node_id, type, value, importance, created_day, archived FROM memory_vectors WHERE node_id IN ({placeholders})",
            tuple(node_ids))

    def get_importance(self, npc_id: str, node_id: str) -> float:
        """获取节点 importance"""
        row = self.db.fetchone(
            "SELECT importance FROM memory_vectors WHERE node_id = ?", (node_id,))
        return row["importance"] if row else 0.5

    def set_archived(self, npc_id: str, node_id: str, archived: bool = True):
        """标记归档状态"""
        self.db.execute(
            "UPDATE memory_vectors SET archived = ? WHERE node_id = ?",
            (1 if archived else 0, node_id))

    def count(self, npc_id: str) -> int:
        """节点数"""
        row = self.db.fetchone(
            "SELECT COUNT(*) as cnt FROM memory_vectors WHERE npc_id = ?", (npc_id,))
        return row["cnt"] if row else 0


def _cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度"""
    dot = sum(ai * bi for ai, bi in zip(a, b))
    na = math.sqrt(sum(ai * ai for ai in a))
    nb = math.sqrt(sum(bi * bi for bi in b))
    if na < 1e-10 or nb < 1e-10:
        return 0.0
    return dot / (na * nb)
