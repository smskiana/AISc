"""日程候选复用的图与向量记忆证据适配层。"""
from __future__ import annotations

from collections import defaultdict

from ..memory.retrieval_contracts import RetrievalRequest


class ScheduleMemoryEvidenceProvider:
    """按 owner 与候选组批量调用现有 retrieval facade。"""

    def __init__(self, retrieve):
        self._retrieve = retrieve

    def enrich(self, npc_id: str, candidates, game_time: str, location_id: str = "") -> tuple[dict[str, dict], dict[str, int]]:
        """返回按组复用的 ID/评分/trace，不保存 embedding。"""
        groups = sorted({item.primary_group for item in candidates})
        result, stats = {}, {"memory_queries": 0, "memory_hits": 0, "memory_without_evidence": 0}
        for group in groups:
            try:
                response = self._retrieve(RetrievalRequest(npc_id=npc_id, query_text=f"日程 {group} 候选的长期记忆证据", location_id=location_id, game_time=game_time, mode="npc_dialogue"))
                diagnostics = response.diagnostics or {}
                paths = diagnostics.get("path_evidence", [])
                vector_hits = diagnostics.get("vector_hit_usage", [])
                evidence_ids = tuple(dict.fromkeys([*response.retrieved_node_ids, *(str(x.get("node_id")) for x in paths if x.get("node_id"))]))
                similarity = max((float(x.get("similarity", 0.0)) for x in vector_hits), default=0.0)
                graph_score = max((float(x.get("score", 0.0)) for x in paths), default=0.0)
                trace_id = str(diagnostics.get("retrieval_trace_id") or "")
                result[group] = {"evidence_ids": evidence_ids, "similarity": similarity, "graph_path_score": graph_score, "trace_ids": (trace_id,) if trace_id else ()}
                stats["memory_queries"] += 1
                stats["memory_hits"] += len(evidence_ids)
                if not evidence_ids:
                    stats["memory_without_evidence"] += 1
            except Exception:
                # 记忆服务不可用不得移除本地物理合法候选。
                result[group] = {}
                stats["memory_without_evidence"] += 1
        return result, stats
