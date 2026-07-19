"""
SQLite 数据库客户端 — 建表 + CRUD 封装。
v0.6: memory_nodes 极简(只存ID) + memory_edges clarity 有向。
"""
import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager


SCHEMA_SQL = """
-- NPC 即时状态
CREATE TABLE IF NOT EXISTS npc_states (
    npc_id TEXT PRIMARY KEY,
    emotion TEXT NOT NULL DEFAULT '平静',
    emotion_baseline TEXT NOT NULL DEFAULT '平静',
    emotion_delta REAL NOT NULL DEFAULT 0.0,
    energy REAL NOT NULL DEFAULT 80.0,
    sociability REAL NOT NULL DEFAULT 50.0,
    sociability_baseline REAL NOT NULL DEFAULT 50.0,
    sociability_delta REAL NOT NULL DEFAULT 0.0,
    current_need TEXT,
    lingering_concern TEXT NOT NULL DEFAULT '',
    next_day_plan_context TEXT NOT NULL DEFAULT '',
    current_location TEXT NOT NULL DEFAULT '',
    current_action TEXT,
    movement_origin TEXT NOT NULL DEFAULT '',
    movement_target TEXT NOT NULL DEFAULT '',
    movement_status TEXT NOT NULL DEFAULT '',
    is_first_encounter INTEGER NOT NULL DEFAULT 1,
    is_asleep INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- NPC 羁绊度矩阵
CREATE TABLE IF NOT EXISTS npc_bonds (
    owner_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    bond REAL NOT NULL DEFAULT 0.0,
    confide_level INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (owner_id, target_id)
);

-- v0.6 记忆图节点: 极简，只存ID
CREATE TABLE IF NOT EXISTS memory_nodes (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    created_at_game_time TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_nodes_subject ON memory_nodes(subject_id);

-- v0.6 记忆图边: clarity 有向清晰度
CREATE TABLE IF NOT EXISTS memory_edges (
    id TEXT PRIMARY KEY,
    node_a TEXT NOT NULL,
    node_b TEXT NOT NULL,
    type TEXT NOT NULL,
    clarity_ab REAL NOT NULL DEFAULT 0.7,
    clarity_ba REAL NOT NULL DEFAULT 0.7,
    target_importance REAL NOT NULL DEFAULT 0.5,
    last_traversed_ab TEXT,
    last_traversed_ba TEXT,
    created_at_game_time TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_edges_a ON memory_edges(node_a);
CREATE INDEX IF NOT EXISTS idx_edges_b ON memory_edges(node_b);
CREATE INDEX IF NOT EXISTS idx_edges_clarity ON memory_edges(clarity_ab DESC, clarity_ba DESC);

-- 短期记忆原文
CREATE TABLE IF NOT EXISTS short_term_memories (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'interaction',
    content TEXT NOT NULL,
    importance REAL NOT NULL DEFAULT 0.5,
    emotional_valence REAL NOT NULL DEFAULT 0.0,
    emotion_type TEXT,
    location TEXT,
    participants TEXT,
    created_at_game_time TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_core INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_stm_subject ON short_term_memories(subject_id);
CREATE INDEX IF NOT EXISTS idx_stm_time ON short_term_memories(created_at_game_time);

-- 玩家记忆
CREATE TABLE IF NOT EXISTS player_memories (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL DEFAULT 'learned_fact',
    about_npc TEXT,
    content TEXT NOT NULL,
    source TEXT,
    game_time TEXT NOT NULL DEFAULT '',
    importance REAL NOT NULL DEFAULT 0.5,
    used_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_pmem_npc ON player_memories(about_npc, importance DESC);

-- 玩家物品
CREATE TABLE IF NOT EXISTS player_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL,
    item_name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    acquired_from TEXT,
    acquired_at_game_time TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 游戏状态
CREATE TABLE IF NOT EXISTS game_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    game_day INTEGER NOT NULL DEFAULT 1,
    game_hour INTEGER NOT NULL DEFAULT 8,
    game_minute INTEGER NOT NULL DEFAULT 0,
    weather TEXT NOT NULL DEFAULT 'sunny',
    player_location TEXT NOT NULL DEFAULT 'player_cafe.doorway',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 夜间生成的熟人基准印象 + 白天微调
CREATE TABLE IF NOT EXISTS npc_impressions (
    owner_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    baseline_impression TEXT NOT NULL DEFAULT '',
    speech_hint TEXT NOT NULL DEFAULT '',
    approach_bias REAL NOT NULL DEFAULT 0.0,
    delta_note TEXT NOT NULL DEFAULT '',
    delta_bias REAL NOT NULL DEFAULT 0.0,
    updated_game_day INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (owner_id, target_id)
);
CREATE INDEX IF NOT EXISTS idx_impressions_owner ON npc_impressions(owner_id);

-- NPC 日程权威快照：跨进程恢复与提交幂等
CREATE TABLE IF NOT EXISTS npc_daily_schedule_snapshots (
    game_day INTEGER NOT NULL,
    npc_id TEXT NOT NULL,
    schedule_revision INTEGER NOT NULL,
    payload_fingerprint TEXT NOT NULL,
    planner_version TEXT NOT NULL DEFAULT '',
    operation_id TEXT NOT NULL,
    status TEXT NOT NULL,
    failure_reason TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (game_day, npc_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_identity
    ON npc_daily_schedule_snapshots(game_day, npc_id, schedule_revision, payload_fingerprint);

-- 融合节点来源追溯
CREATE TABLE IF NOT EXISTS memory_merge_sources (
    merged_node_id TEXT NOT NULL,
    source_node_id TEXT NOT NULL,
    npc_id TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT '',
    source_value TEXT NOT NULL DEFAULT '',
    similarity REAL NOT NULL DEFAULT 0.0,
    created_at_game_time TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (merged_node_id, source_node_id)
);
CREATE INDEX IF NOT EXISTS idx_merge_sources_npc ON memory_merge_sources(npc_id, merged_node_id);

-- 检索诊断日志
CREATE TABLE IF NOT EXISTS memory_retrieval_logs (
    id TEXT PRIMARY KEY,
    npc_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    game_time TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    graph_nodes INTEGER NOT NULL DEFAULT 0,
    vector_fallback INTEGER NOT NULL DEFAULT 0,
    final_nodes INTEGER NOT NULL DEFAULT 0,
    selected_edges INTEGER NOT NULL DEFAULT 0,
    llm_route_calls INTEGER NOT NULL DEFAULT 0,
    local_route_skips INTEGER NOT NULL DEFAULT 0,
    hit_merged_count INTEGER NOT NULL DEFAULT 0,
    elapsed_sec REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_retrieval_logs_npc ON memory_retrieval_logs(npc_id, target_id, mode, created_at);

-- 冷启动初始知识投影来源与权限审计
CREATE TABLE IF NOT EXISTS memory_initial_projections (
    projection_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL UNIQUE,
    observer_id TEXT NOT NULL,
    source_fact_id TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    knowledge_scope TEXT NOT NULL,
    visibility_rule TEXT NOT NULL,
    visibility_reason TEXT NOT NULL,
    source_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    importance REAL NOT NULL,
    subject_ids_json TEXT NOT NULL,
    location_ids_json TEXT NOT NULL,
    created_day INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_initial_projections_observer
    ON memory_initial_projections(observer_id, created_at);
CREATE INDEX IF NOT EXISTS idx_initial_projections_fact
    ON memory_initial_projections(source_fact_id, observer_id);
"""


class SQLiteClient:
    """SQLite 数据库客户端"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            self._apply_pre_schema_migrations(conn)
            conn.executescript(SCHEMA_SQL)
            self._apply_migrations(conn)
            conn.execute("INSERT OR IGNORE INTO game_state (id) VALUES (1)")
            conn.commit()

    def _apply_pre_schema_migrations(self, conn) -> None:
        """在建索引前补齐会阻断 SCHEMA_SQL 的旧图表字段。"""
        if not self._table_exists(conn, "memory_edges"):
            return

        existing = self._table_columns(conn, "memory_edges")
        self._ensure_columns(conn, "memory_edges", {
            "clarity_ab": "REAL NOT NULL DEFAULT 0.7",
            "clarity_ba": "REAL NOT NULL DEFAULT 0.7",
            "target_importance": "REAL NOT NULL DEFAULT 0.5",
        })
        if "weight_ab" in existing:
            conn.execute("UPDATE memory_edges SET clarity_ab = COALESCE(weight_ab, clarity_ab)")
        if "weight_ba" in existing:
            conn.execute("UPDATE memory_edges SET clarity_ba = COALESCE(weight_ba, clarity_ba)")
        if "weight_ab" in existing or "weight_ba" in existing:
            conn.execute(
                """UPDATE memory_edges
                   SET target_importance = MAX(
                       COALESCE(weight_ab, 0.5),
                       COALESCE(weight_ba, 0.5),
                       target_importance
                   )"""
            )

    def _apply_migrations(self, conn) -> None:
        """为旧存档补齐新增字段，不要求删表重建。"""
        self._ensure_columns(conn, "npc_states", {
            "emotion_baseline": "TEXT NOT NULL DEFAULT '平静'",
            "emotion_delta": "REAL NOT NULL DEFAULT 0.0",
            "sociability_baseline": "REAL NOT NULL DEFAULT 50.0",
            "sociability_delta": "REAL NOT NULL DEFAULT 0.0",
            "lingering_concern": "TEXT NOT NULL DEFAULT ''",
            "next_day_plan_context": "TEXT NOT NULL DEFAULT ''",
            "movement_origin": "TEXT NOT NULL DEFAULT ''",
            "movement_target": "TEXT NOT NULL DEFAULT ''",
            "movement_status": "TEXT NOT NULL DEFAULT ''",
        })
        self._ensure_table(
            conn,
            "npc_impressions",
            """
            CREATE TABLE IF NOT EXISTS npc_impressions (
                owner_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                baseline_impression TEXT NOT NULL DEFAULT '',
                speech_hint TEXT NOT NULL DEFAULT '',
                approach_bias REAL NOT NULL DEFAULT 0.0,
                delta_note TEXT NOT NULL DEFAULT '',
                delta_bias REAL NOT NULL DEFAULT 0.0,
                updated_game_day INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (owner_id, target_id)
            )
            """,
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_impressions_owner ON npc_impressions(owner_id)")
        self._ensure_table(
            conn,
            "memory_merge_sources",
            """
            CREATE TABLE IF NOT EXISTS memory_merge_sources (
                merged_node_id TEXT NOT NULL,
                source_node_id TEXT NOT NULL,
                npc_id TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT '',
                source_value TEXT NOT NULL DEFAULT '',
                similarity REAL NOT NULL DEFAULT 0.0,
                created_at_game_time TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (merged_node_id, source_node_id)
            )
            """,
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_merge_sources_npc ON memory_merge_sources(npc_id, merged_node_id)")
        self._ensure_table(
            conn,
            "memory_retrieval_logs",
            """
            CREATE TABLE IF NOT EXISTS memory_retrieval_logs (
                id TEXT PRIMARY KEY,
                npc_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                game_time TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                graph_nodes INTEGER NOT NULL DEFAULT 0,
                vector_fallback INTEGER NOT NULL DEFAULT 0,
                final_nodes INTEGER NOT NULL DEFAULT 0,
                selected_edges INTEGER NOT NULL DEFAULT 0,
                llm_route_calls INTEGER NOT NULL DEFAULT 0,
                local_route_skips INTEGER NOT NULL DEFAULT 0,
                hit_merged_count INTEGER NOT NULL DEFAULT 0,
                elapsed_sec REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_retrieval_logs_npc ON memory_retrieval_logs(npc_id, target_id, mode, created_at)")
        self._ensure_table(
            conn,
            "memory_initial_projections",
            """
            CREATE TABLE IF NOT EXISTS memory_initial_projections (
                projection_id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL UNIQUE,
                observer_id TEXT NOT NULL,
                source_fact_id TEXT NOT NULL,
                fact_type TEXT NOT NULL,
                knowledge_scope TEXT NOT NULL,
                visibility_rule TEXT NOT NULL,
                visibility_reason TEXT NOT NULL,
                source_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                importance REAL NOT NULL,
                subject_ids_json TEXT NOT NULL,
                location_ids_json TEXT NOT NULL,
                created_day INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_initial_projections_observer "
            "ON memory_initial_projections(observer_id, created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_initial_projections_fact "
            "ON memory_initial_projections(source_fact_id, observer_id)"
        )

    @staticmethod
    def _table_exists(conn, table: str) -> bool:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _table_columns(conn, table: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row[1] for row in rows}

    @staticmethod
    def _ensure_columns(conn, table: str, columns: dict[str, str]) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {row[1] for row in rows}
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    @staticmethod
    def _ensure_table(conn, table: str, create_sql: str) -> None:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if row is None:
            conn.execute(create_sql)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._conn() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor

    def get_daily_schedule_snapshot(self, game_day: int, npc_id: str) -> dict | None:
        """读取跨进程可恢复的 NPC 日程快照。"""
        return self.fetchone(
            "SELECT * FROM npc_daily_schedule_snapshots WHERE game_day = ? AND npc_id = ?",
            (game_day, npc_id),
        )

    def save_daily_schedule_snapshot(self, snapshot: dict) -> None:
        """以同日日程主键原子保存最新权威快照。"""
        self.execute(
            """INSERT INTO npc_daily_schedule_snapshots
               (game_day, npc_id, schedule_revision, payload_fingerprint,
                planner_version, operation_id, status, failure_reason, payload_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(game_day, npc_id) DO UPDATE SET
                 schedule_revision=excluded.schedule_revision,
                 payload_fingerprint=excluded.payload_fingerprint,
                 planner_version=excluded.planner_version,
                 operation_id=excluded.operation_id,
                 status=excluded.status,
                 failure_reason=excluded.failure_reason,
                 payload_json=excluded.payload_json,
                 updated_at=datetime('now')""",
            (snapshot["game_day"], snapshot["npc_id"], snapshot["schedule_revision"],
             snapshot["payload_fingerprint"], snapshot.get("planner_version", ""),
             snapshot["operation_id"], snapshot.get("status", "generated"),
             snapshot.get("failure_reason", ""), snapshot["payload_json"]),
        )

    def purge_daily_schedule_snapshots(self) -> list[dict]:
        """在单个 SQLite 事务中返回并删除全部可重建日程快照。"""
        with self._conn() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                rows = [dict(row) for row in conn.execute("SELECT * FROM npc_daily_schedule_snapshots")]
                conn.execute("DELETE FROM npc_daily_schedule_snapshots")
                conn.commit()
                return rows
            except Exception:
                conn.rollback()
                raise

    def restore_daily_schedule_snapshots(self, rows: list[dict]) -> None:
        """在新游戏复合清理失败时恢复本次删除的日程快照。"""
        if not rows:
            return
        with self._conn() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.executemany(
                    """INSERT OR REPLACE INTO npc_daily_schedule_snapshots
                       (game_day,npc_id,schedule_revision,payload_fingerprint,planner_version,
                        operation_id,status,failure_reason,payload_json,updated_at)
                       VALUES (:game_day,:npc_id,:schedule_revision,:payload_fingerprint,:planner_version,
                        :operation_id,:status,:failure_reason,:payload_json,:updated_at)""",
                    rows,
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    # ═══════════════════════════════════════════
    # 节点 (v0.6 极简)
    # ═══════════════════════════════════════════

    def insert_node(self, node: dict) -> None:
        """插入记忆图节点（仅 ID + subject_id）"""
        columns = self.fetchall("PRAGMA table_info(memory_nodes)")
        column_names = {row["name"] for row in columns}
        insert_columns = ["id", "subject_id", "created_at_game_time"]
        values = [node["id"], node["subject_id"], node.get("created_at_game_time", "")]
        if "type" in column_names:
            insert_columns.append("type")
            values.append(node.get("type", "event"))
        if "value" in column_names:
            insert_columns.append("value")
            values.append(node.get("value", node["id"]))

        placeholders = ", ".join("?" for _ in insert_columns)
        column_sql = ", ".join(insert_columns)
        self.execute(
            f"INSERT OR REPLACE INTO memory_nodes ({column_sql}) VALUES ({placeholders})",
            tuple(values),
        )

    def delete_node(self, node_id: str) -> None:
        self.execute("DELETE FROM memory_nodes WHERE id = ?", (node_id,))

    def get_nodes_by_npc(self, npc_id: str) -> list[dict]:
        return self.fetchall(
            "SELECT id FROM memory_nodes WHERE subject_id = ?", (npc_id,))

    def insert_initial_projection(self, projection: dict) -> None:
        """写入一条冷启动投影来源，使用稳定 projection_id 幂等覆盖。"""
        self.execute(
            """INSERT OR REPLACE INTO memory_initial_projections
               (projection_id, node_id, observer_id, source_fact_id, fact_type,
                knowledge_scope, visibility_rule, visibility_reason, source_type,
                confidence, importance, subject_ids_json, location_ids_json,
                created_day)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                projection["projection_id"],
                projection["node_id"],
                projection["observer_id"],
                projection["source_fact_id"],
                projection["fact_type"],
                projection["knowledge_scope"],
                projection["visibility_rule"],
                projection["visibility_reason"],
                projection["source_type"],
                projection["confidence"],
                projection["importance"],
                json.dumps(projection.get("subject_ids", []), ensure_ascii=False),
                json.dumps(projection.get("location_ids", []), ensure_ascii=False),
                projection["created_day"],
            ),
        )

    def insert_initial_projections(self, projections: list[dict]) -> None:
        """批量写入冷启动投影来源，保持与单条 CRUD 相同字段口径。"""
        for projection in projections:
            self.insert_initial_projection(projection)

    def get_initial_projections(
        self,
        observer_id: str,
        source_fact_id: str | None = None,
    ) -> list[dict]:
        """按观察者查询投影来源，可选按稳定事实 ID 收窄。"""
        sql = "SELECT * FROM memory_initial_projections WHERE observer_id = ?"
        params: list[str] = [observer_id]
        if source_fact_id:
            sql += " AND source_fact_id = ?"
            params.append(source_fact_id)
        sql += " ORDER BY projection_id"
        return self.fetchall(sql, tuple(params))

    def get_initial_projections_by_fact(self, source_fact_id: str) -> list[dict]:
        """按来源事实查询所有观察者的投影来源。"""
        return self.fetchall(
            "SELECT * FROM memory_initial_projections WHERE source_fact_id = ? ORDER BY observer_id",
            (source_fact_id,),
        )

    def get_initial_projection_edges(self, node_ids: list[str]) -> list[dict]:
        """查询投影节点实际连接的边，供诊断追溯确定性边 ID。"""
        if not node_ids:
            return []
        placeholders = ",".join("?" for _ in node_ids)
        return self.fetchall(
            f"""SELECT id, node_a, node_b, type, clarity_ab, clarity_ba,
                       target_importance, created_at_game_time
                FROM memory_edges
                WHERE node_a IN ({placeholders}) OR node_b IN ({placeholders})
                ORDER BY id""",
            tuple(node_ids + node_ids),
        )

    def get_orphan_nodes(self, npc_id: str) -> list[str]:
        """查找无边的孤立节点（用于午夜清理）"""
        rows = self.fetchall(
            """SELECT n.id FROM memory_nodes n
               WHERE n.subject_id = ?
               AND NOT EXISTS (SELECT 1 FROM memory_edges WHERE node_a = n.id OR node_b = n.id)""",
            (npc_id,))
        return [r["id"] for r in rows]

    # ═══════════════════════════════════════════
    # 边 (v0.6 clarity)
    # ═══════════════════════════════════════════

    def insert_edge(self, edge: dict) -> None:
        """插入边（clarity 有向 + target_importance 冗余）"""
        self.execute(
            """INSERT OR REPLACE INTO memory_edges
               (id, node_a, node_b, type, clarity_ab, clarity_ba,
                target_importance, created_at_game_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (edge["id"], edge["node_a"], edge["node_b"], edge["type"],
             edge.get("clarity_ab", 0.7), edge.get("clarity_ba", 0.7),
             edge.get("target_importance", 0.5),
             edge.get("created_at_game_time", ""))
        )

    def delete_edge(self, edge_id: str) -> None:
        self.execute("DELETE FROM memory_edges WHERE id = ?", (edge_id,))

    def get_edges_touching_node_ids(self, node_ids: list[str]) -> list[dict]:
        """查询任一指定节点相连的全部边，供融合继承旧邻域使用。"""
        if not node_ids:
            return []

        placeholders = ",".join("?" for _ in node_ids)
        return self.fetchall(
            f"""SELECT id, node_a, node_b, type, clarity_ab, clarity_ba,
                       target_importance, created_at_game_time
                FROM memory_edges
                WHERE node_a IN ({placeholders}) OR node_b IN ({placeholders})""",
            tuple(node_ids + node_ids),
        )

    def delete_edges_touching_node_ids(self, node_ids: list[str]) -> None:
        """删除任一指定节点相连的边，供融合后旧图节点退场使用。"""
        if not node_ids:
            return

        placeholders = ",".join("?" for _ in node_ids)
        self.execute(
            f"DELETE FROM memory_edges WHERE node_a IN ({placeholders}) OR node_b IN ({placeholders})",
            tuple(node_ids + node_ids),
        )

    def get_out_edges(self, node_id: str, limit: int = 15) -> list[dict]:
        """获取从 node_id 出发的边（按 clarity_ab 降序）"""
        return self.fetchall(
            """SELECT id, node_a, node_b, type, clarity_ab, clarity_ba,
                      target_importance
               FROM memory_edges
               WHERE node_a = ?
               ORDER BY clarity_ab DESC
               LIMIT ?""",
            (node_id, limit))

    def get_all_edges_for_decay(self, npc_id: str) -> list[dict]:
        """获取 NPC 所有可衰减的边（联想边，排除结构边）"""
        # 结构边类型不衰减
        STRUCTURAL_TYPES = ("involved", "sequenced", "located_at", "contains")
        placeholders = ",".join("?" for _ in STRUCTURAL_TYPES)
        return self.fetchall(
            f"""SELECT e.id, e.clarity_ab, e.clarity_ba, e.target_importance, e.type
                FROM memory_edges e
                WHERE (e.node_a IN (SELECT id FROM memory_nodes WHERE subject_id = ?)
                   OR e.node_b IN (SELECT id FROM memory_nodes WHERE subject_id = ?))
                  AND e.type NOT IN ({placeholders})
                  AND (e.clarity_ab > 0.05 OR e.clarity_ba > 0.05)""",
            (npc_id, npc_id, *STRUCTURAL_TYPES))

    def decay_edge_clarity(self, edge_id: str, clarity_ab: float,
                           clarity_ba: float) -> None:
        """更新边的清晰度值"""
        self.execute(
            "UPDATE memory_edges SET clarity_ab = ?, clarity_ba = ? WHERE id = ?",
            (round(clarity_ab, 4), round(clarity_ba, 4), edge_id))

    def mark_edge_traversed(self, edge_id: str, direction: str) -> None:
        """标记边被遍历（用于清晰度恢复）"""
        col = "last_traversed_ab" if direction == "ab" else "last_traversed_ba"
        self.execute(
            f"UPDATE memory_edges SET {col} = datetime('now') WHERE id = ?",
            (edge_id,))

    def get_edges_below_clarity(self, npc_id: str, threshold: float = 0.05) -> list[dict]:
        """获取清晰度低于阈值的边（用于删除）"""
        return self.fetchall(
            """SELECT e.id, e.node_a, e.node_b
               FROM memory_edges e
               WHERE (e.node_a IN (SELECT id FROM memory_nodes WHERE subject_id = ?)
                   OR e.node_b IN (SELECT id FROM memory_nodes WHERE subject_id = ?))
                 AND e.clarity_ab < ? AND e.clarity_ba < ?""",
            (npc_id, threshold, threshold))

    # ═══════════════════════════════════════════
    # 图查询辅助
    # ═══════════════════════════════════════════

    def get_neighbors(self, node_id: str, limit: int = 20) -> list[dict]:
        """查询节点的邻边（按 clarity 排序）"""
        sql = """SELECT id, node_a, node_b, type, clarity_ab, clarity_ba,
                        target_importance
                 FROM memory_edges
                 WHERE node_a = ? OR node_b = ?
                 ORDER BY MAX(clarity_ab, clarity_ba) DESC
                 LIMIT ?"""
        return self.fetchall(sql, (node_id, node_id, limit))

    def get_directional_neighbors(self, node_id: str, limit: int = 20) -> list[dict]:
        """查询节点邻边，并返回从当前节点出发时的方向语义。"""
        sql = """SELECT id, node_a, node_b, type, clarity_ab, clarity_ba,
                        target_importance,
                        CASE WHEN node_a = ? THEN node_b ELSE node_a END AS neighbor_id,
                        CASE WHEN node_a = ? THEN 'ab' ELSE 'ba' END AS direction,
                        CASE WHEN node_a = ? THEN clarity_ab ELSE clarity_ba END AS directional_clarity
                 FROM memory_edges
                 WHERE node_a = ? OR node_b = ?
                 ORDER BY directional_clarity DESC
                 LIMIT ?"""
        return self.fetchall(sql, (node_id, node_id, node_id, node_id, node_id, limit))

    def get_directional_neighbors_batch(self, node_ids: list[str], limit_per_node: int = 20) -> dict[str, list[dict]]:
        """批量读取多个前沿节点的方向邻边，按节点在领域适配器内限流。"""
        if not node_ids or limit_per_node <= 0:
            return {}
        placeholders = ",".join("?" for _ in node_ids)
        rows = self.fetchall(
            f"""SELECT id, node_a, node_b, type, clarity_ab, clarity_ba,
                       target_importance
                FROM memory_edges
                WHERE node_a IN ({placeholders}) OR node_b IN ({placeholders})
                ORDER BY MAX(clarity_ab, clarity_ba) DESC""",
            (*node_ids, *node_ids),
        )
        result: dict[str, list[dict]] = {node_id: [] for node_id in node_ids}
        for row in rows:
            for node_id in node_ids:
                if node_id not in {row.get("node_a"), row.get("node_b")}:
                    continue
                current_is_a = row.get("node_a") == node_id
                enriched = {
                    **row,
                    "neighbor_id": row.get("node_b") if current_is_a else row.get("node_a"),
                    "direction": "ab" if current_is_a else "ba",
                    "directional_clarity": row.get("clarity_ab") if current_is_a else row.get("clarity_ba"),
                }
                if len(result[node_id]) < limit_per_node:
                    result[node_id].append(enriched)
        return result

    def get_node_degree(self, node_id: str) -> int:
        """节点连接边数"""
        row = self.fetchone(
            "SELECT COUNT(*) as cnt FROM memory_edges WHERE node_a = ? OR node_b = ?",
            (node_id, node_id))
        return row["cnt"] if row else 0

    def insert_merge_source(self, source: dict) -> None:
        """记录融合节点的来源节点，供调试和来源追溯使用。"""
        self.execute(
            """INSERT OR REPLACE INTO memory_merge_sources
               (merged_node_id, source_node_id, npc_id, source_type,
                source_value, similarity, created_at_game_time)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                source["merged_node_id"],
                source["source_node_id"],
                source["npc_id"],
                source.get("source_type", ""),
                source.get("source_value", ""),
                source.get("similarity", 0.0),
                source.get("created_at_game_time", ""),
            ),
        )

    def get_merge_sources(self, npc_id: str, merged_node_ids: list[str]) -> list[dict]:
        """批量查询融合来源。"""
        if not merged_node_ids:
            return []

        placeholders = ",".join("?" for _ in merged_node_ids)
        return self.fetchall(
            f"""SELECT merged_node_id, source_node_id, source_type,
                       source_value, similarity, created_at_game_time
                FROM memory_merge_sources
                WHERE npc_id = ? AND merged_node_id IN ({placeholders})
                ORDER BY created_at DESC""",
            (npc_id, *merged_node_ids),
        )

    def insert_retrieval_log(self, row: dict) -> None:
        """写入一次记忆检索诊断日志。"""
        self.execute(
            """INSERT INTO memory_retrieval_logs
               (id, npc_id, target_id, mode, game_time, location,
                graph_nodes, vector_fallback, final_nodes, selected_edges,
                llm_route_calls, local_route_skips, hit_merged_count, elapsed_sec)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["id"],
                row["npc_id"],
                row["target_id"],
                row["mode"],
                row.get("game_time", ""),
                row.get("location", ""),
                row.get("graph_nodes", 0),
                row.get("vector_fallback", 0),
                row.get("final_nodes", 0),
                row.get("selected_edges", 0),
                row.get("llm_route_calls", 0),
                row.get("local_route_skips", 0),
                row.get("hit_merged_count", 0),
                row.get("elapsed_sec", 0.0),
            ),
        )
