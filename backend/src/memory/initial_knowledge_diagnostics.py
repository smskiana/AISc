"""冷启动初始知识投影的只读诊断快照构建。"""
from __future__ import annotations

from pathlib import Path

from .initial_knowledge import KnowledgeRelationshipContext, load_initial_knowledge, project_initial_knowledge


KNOWN_INITIAL_KNOWLEDGE_IDS = frozenset({
    "player", "sakura", "chihaya", "kazuha", "tatsunosuke", "kujo",
})


def build_initial_knowledge_snapshot(
    db,
    vector_store,
    config_path: Path,
    npc_id: str,
    source_fact_id: str | None = None,
    include_excluded: bool = False,
) -> dict:
    """从事实配置、SQLite 来源表和向量层构建结构化只读快照。"""
    if npc_id not in KNOWN_INITIAL_KNOWLEDGE_IDS:
        return {
            "npc_id": npc_id,
            "count": 0,
            "items": [],
            "failure_reason": "unknown_observer_id",
        }

    facts = load_initial_knowledge(config_path, known_ids=KNOWN_INITIAL_KNOWLEDGE_IDS)
    fact_by_id = {fact.fact_id: fact for fact in facts}
    if source_fact_id and source_fact_id not in fact_by_id:
        return {
            "npc_id": npc_id,
            "count": 0,
            "items": [],
            "failure_reason": "source_fact_not_found",
        }

    result = project_initial_knowledge(
        facts,
        npc_id,
        KnowledgeRelationshipContext(community_observer_ids=KNOWN_INITIAL_KNOWLEDGE_IDS),
    )
    projected_by_fact = {item.source_fact_id: item for item in result.projections}
    decision_by_fact = {item.fact_id: item for item in result.excluded}
    selected_facts = facts if not source_fact_id else (fact_by_id[source_fact_id],)
    items: list[dict] = []
    for fact in selected_facts:
        projected = projected_by_fact.get(fact.fact_id)
        if projected is not None:
            items.append(_included_snapshot(db, vector_store, projected))
        elif include_excluded:
            items.append(_excluded_snapshot(decision_by_fact[fact.fact_id], fact))
    return {
        "npc_id": npc_id,
        "count": len(items),
        "items": items,
        "failure_reason": "",
    }


def _included_snapshot(db, vector_store, projection) -> dict:
    """组合已纳入投影的来源元数据、向量内容和实际边。"""
    metadata_rows = db.get_initial_projections(
        projection.observer_id,
        projection.source_fact_id,
    )
    metadata = metadata_rows[0] if metadata_rows else None
    if metadata is None:
        return _projection_payload(
            projection,
            status="included",
            failure_reason="projection_metadata_missing",
        )

    node_id = metadata["node_id"]
    node = db.fetchone("SELECT id FROM memory_nodes WHERE id = ?", (node_id,))
    if node is None:
        return _projection_payload(
            projection,
            status="included",
            projection_id=metadata["projection_id"],
            node_id=node_id,
            failure_reason="graph_node_missing",
        )

    vector_rows = []
    if vector_store and hasattr(vector_store, "get_batch"):
        vector_rows = vector_store.get_batch(projection.observer_id, [node_id])
    vector_node = vector_rows[0] if vector_rows else None
    failure_reason = "" if vector_node else "vector_node_missing"
    edges = db.get_initial_projection_edges([node_id])
    person_node_ids = _person_node_ids(db, vector_store, projection.observer_id, edges)
    payload = _projection_payload(
        projection,
        status="included",
        projection_id=metadata["projection_id"],
        node_id=node_id,
        value_preview=str((vector_node or {}).get("value", ""))[:240],
        edge_ids=[edge["id"] for edge in edges],
        person_node_ids=person_node_ids,
        failure_reason=failure_reason,
    )
    payload["source_type"] = metadata["source_type"]
    payload["confidence"] = metadata["confidence"]
    payload["importance"] = metadata["importance"]
    payload["created_day"] = metadata["created_day"]
    return payload


def _excluded_snapshot(decision, fact) -> dict:
    """构造不含运行时节点和边标识的排除诊断项。"""
    return {
        "observer_id": decision.observer_id,
        "fact_id": fact.fact_id,
        "status": "excluded",
        "projection_id": "",
        "node_id": "",
        "value_preview": "",
        "knowledge_scope": fact.knowledge_scope.value,
        "visibility_rule": decision.rule,
        "visibility_reason": decision.reason,
        "source_type": fact.source_type.value,
        "confidence": fact.confidence,
        "importance": fact.importance,
        "subject_ids": list(fact.subject_ids),
        "location_ids": list(fact.location_ids),
        "created_day": fact.created_day,
        "edge_ids": [],
        "person_node_ids": [],
        "failure_reason": "",
    }


def _projection_payload(
    projection,
    status: str,
    projection_id: str = "",
    node_id: str = "",
    value_preview: str = "",
    edge_ids: list[str] | None = None,
    person_node_ids: list[str] | None = None,
    failure_reason: str = "",
) -> dict:
    """输出 included/excluded 共用的稳定字段。"""
    return {
        "observer_id": projection.observer_id,
        "fact_id": projection.source_fact_id,
        "status": status,
        "projection_id": projection_id,
        "node_id": node_id,
        "value_preview": value_preview,
        "knowledge_scope": projection.knowledge_scope,
        "visibility_rule": projection.visibility_rule,
        "visibility_reason": projection.visibility_reason,
        "source_type": projection.source_type,
        "confidence": projection.confidence,
        "importance": projection.importance,
        "subject_ids": list(projection.subject_ids),
        "location_ids": list(projection.location_ids),
        "created_day": projection.created_day,
        "edge_ids": edge_ids or [],
        "person_node_ids": person_node_ids or [],
        "failure_reason": failure_reason,
    }


def _person_node_ids(db, vector_store, npc_id: str, edges: list[dict]) -> list[str]:
    """从向量节点类型识别投影实际连接的人物节点。"""
    node_rows = db.get_nodes_by_npc(npc_id)
    node_ids = [row["id"] for row in node_rows]
    if not vector_store or not hasattr(vector_store, "get_batch"):
        return []
    vector_rows = vector_store.get_batch(npc_id, node_ids)
    person_ids = {row["node_id"] for row in vector_rows if row.get("type") == "person"}
    edge_node_ids = {edge["node_a"] for edge in edges} | {edge["node_b"] for edge in edges}
    return sorted(person_ids & edge_node_ids)
