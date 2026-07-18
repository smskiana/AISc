"""
FastAPI 入口 — 仅保留传输层路由与运行时委托。
"""
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from .protocol.codec import ProtocolDecodeError
from .protocol.session import ProtocolSession

from . import config as cfg_module
from .application.runtime import GameRuntime
from .dialogue.reply_suggestion_diagnostics import reply_suggestion_trace_store
from .memory.initial_knowledge_diagnostics import build_initial_knowledge_snapshot
from .memory.midnight_coordinator import midnight_snapshot_store
from .memory.retrieval import RetrievalRequest
from .world.clock import game_clock

logger = logging.getLogger("sakurabashi")

runtime = GameRuntime()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await runtime.start()
    yield
    await runtime.stop()


app = FastAPI(title="樱桥通 Backend", version="0.2.0", lifespan=lifespan)


def _services():
    return runtime.require_services()


@app.get("/api/health")
async def health():
    return JSONResponse(
        {
            "status": "ok",
            "version": "0.2.0",
            "npc_count": len(cfg_module.config.npc_ids),
            "locations_zones": len(cfg_module.config.locations.get("zones", {})),
            "actions_categories": len(cfg_module.config.actions.get("actions", {})),
            "items_count": len(cfg_module.config.items),
            "llm": f"{cfg_module.config.llm_provider}/{cfg_module.config.llm_model}",
            "llm_thinking_mode": cfg_module.config.llm_thinking_mode or "provider_default",
            "game_time": game_clock.time_str(),
        }
    )


@app.get("/api/npc/{npc_id}/status")
async def npc_status(npc_id: str):
    row = _services().sqlite.fetchone("SELECT * FROM npc_states WHERE npc_id = ?", (npc_id,))
    if not row:
        return JSONResponse({"error": "npc not found"}, status_code=404)
    return JSONResponse(row)


@app.get("/api/npc/{npc_id}/memories")
async def npc_memories(npc_id: str, limit: int = 20):
    """查询 NPC 的记忆节点（SQLite 基础信息 + 向量层补充）。"""
    services = _services()
    nodes = services.sqlite.fetchall(
        "SELECT * FROM memory_nodes WHERE subject_id = ? ORDER BY created_at DESC LIMIT ?",
        (npc_id, limit),
    )
    if not nodes:
        return JSONResponse({"npc_id": npc_id, "count": 0, "nodes": []})

    vector_store = services.vector_store
    if vector_store and hasattr(vector_store, "get_batch"):
        node_ids = [node["id"] for node in nodes]
        batch = vector_store.get_batch(npc_id, node_ids)
        batch_by_id = {item["node_id"]: item for item in batch}
        enriched = []
        for node in nodes:
            extra = batch_by_id.get(node["id"], {})
            enriched.append(
                {
                    **node,
                    "type": extra.get("type", ""),
                    "value": extra.get("value", ""),
                    "importance": extra.get("importance", 0.5),
                    "archived": extra.get("archived", 0),
                }
            )
        return JSONResponse({"npc_id": npc_id, "count": len(enriched), "nodes": enriched})

    return JSONResponse({"npc_id": npc_id, "count": len(nodes), "nodes": nodes})


@app.get("/api/npc/{npc_id}/graph")
async def npc_graph(npc_id: str, detail: bool = False, limit: int = 50):
    """查询 NPC 记忆图；detail=true 时返回节点、边、融合来源和检索诊断。"""
    services = _services()
    limit = max(1, min(int(limit), 100))
    node_count = services.sqlite.fetchone(
        "SELECT COUNT(*) as cnt FROM memory_nodes WHERE subject_id = ?",
        (npc_id,),
    )
    edge_count = services.sqlite.fetchone(
        """SELECT COUNT(*) as cnt FROM memory_edges
           WHERE node_a IN (SELECT id FROM memory_nodes WHERE subject_id = ?)
              OR node_b IN (SELECT id FROM memory_nodes WHERE subject_id = ?)""",
        (npc_id, npc_id),
    )
    payload = {
        "npc_id": npc_id,
        "node_count": node_count["cnt"] if node_count else 0,
        "edge_count": edge_count["cnt"] if edge_count else 0,
    }
    if not detail:
        return JSONResponse(payload)

    nodes = services.sqlite.fetchall(
        """SELECT id, subject_id, created_at_game_time, created_at
           FROM memory_nodes
           WHERE subject_id = ?
           ORDER BY created_at DESC
           LIMIT ?""",
        (npc_id, limit),
    )
    node_ids = [node["id"] for node in nodes]
    extra_by_id = {}
    if services.vector_store and hasattr(services.vector_store, "get_batch") and node_ids:
        batch = services.vector_store.get_batch(npc_id, node_ids)
        extra_by_id = {item["node_id"]: item for item in batch}

    merge_sources = services.sqlite.get_merge_sources(npc_id, node_ids)
    sources_by_merged: dict[str, list[dict]] = {}
    for source in merge_sources:
        sources_by_merged.setdefault(source["merged_node_id"], []).append(source)

    enriched_nodes = []
    for node in nodes:
        extra = extra_by_id.get(node["id"], {})
        enriched_nodes.append({
            **node,
            "type": extra.get("type", ""),
            "value": extra.get("value", ""),
            "importance": extra.get("importance", 0.5),
            "created_day": extra.get("created_day", 1),
            "archived": extra.get("archived", 0),
            "merge_sources": sources_by_merged.get(node["id"], []),
        })

    edges = services.sqlite.fetchall(
        """SELECT id, node_a, node_b, type, clarity_ab, clarity_ba,
                  target_importance, last_traversed_ab, last_traversed_ba,
                  created_at_game_time
           FROM memory_edges
           WHERE node_a IN (SELECT id FROM memory_nodes WHERE subject_id = ?)
              OR node_b IN (SELECT id FROM memory_nodes WHERE subject_id = ?)
           ORDER BY MAX(clarity_ab, clarity_ba) DESC
           LIMIT ?""",
        (npc_id, npc_id, limit),
    )
    retrieval_logs = services.sqlite.fetchall(
        """SELECT npc_id, target_id, mode, game_time, location,
                  graph_nodes, vector_fallback, final_nodes, selected_edges,
                  llm_route_calls, local_route_skips, hit_merged_count,
                  elapsed_sec, created_at
           FROM memory_retrieval_logs
           WHERE npc_id = ?
           ORDER BY created_at DESC
           LIMIT 10""",
        (npc_id,),
    )
    payload.update({
        "nodes": enriched_nodes,
        "edges": edges,
        "recent_retrievals": retrieval_logs,
    })
    return JSONResponse(
        payload
    )


@app.get("/api/npc/{npc_id}/initial_knowledge_projection_snapshot")
async def initial_knowledge_projection_snapshot(
    npc_id: str,
    source_fact_id: str | None = None,
    include_excluded: bool = False,
):
    """返回冷启动初始知识的权限决定、实际节点和实际边。"""
    try:
        services = _services()
        payload = build_initial_knowledge_snapshot(
            services.sqlite,
            services.vector_store,
            cfg_module.CONFIG_DIR / "initial_knowledge.json",
            npc_id,
            source_fact_id,
            include_excluded,
        )
    except ValueError as error:
        return JSONResponse(
            {"npc_id": npc_id, "count": 0, "items": [], "failure_reason": str(error)},
            status_code=400,
        )
    return JSONResponse(payload)


@app.get("/api/memory/retrieval_snapshot")
async def memory_retrieval_snapshot(
    retrieval_trace_id: str | None = None,
    npc_id: str | None = None,
    mode: str | None = None,
    strategy: str | None = None,
    limit: int = 50,
):
    """返回有界的通用记忆检索 trace，不让 Unity 重建后端图。"""
    services = _services()
    items = services.retrieval.trace_store.snapshot(retrieval_trace_id, npc_id, mode, strategy, limit)
    return JSONResponse({
        "count": len(items),
        "items": items,
    })


@app.get("/api/npc/daily_schedule_trace")
async def daily_schedule_trace(operation_id: str | None = None, npc_id: str | None = None):
    """返回日程三层决策的安全 owner trace，供 aisc_debug 读取。"""
    items = _services().behavior.daily_schedule_diagnostics(operation_id or "", npc_id or "")
    return JSONResponse({"count": len(items), "items": items})


@app.get("/api/memory/midnight_snapshot")
async def midnight_snapshot():
    """返回当前或最近一次午夜维护的结构化阶段与结果。"""
    return JSONResponse(midnight_snapshot_store.snapshot())


@app.get("/api/dialogue/player_reply_suggestion_snapshot")
async def player_reply_suggestion_snapshot(
    reply_trace_id: str | None = None,
    npc_id: str | None = None,
    limit: int = 50,
):
    """返回有界玩家快捷回复 trace，不暴露完整 Prompt 或原始 LLM 输出。"""
    items = reply_suggestion_trace_store.snapshot(reply_trace_id, npc_id, limit)
    return JSONResponse({
        "count": len(items),
        "items": items,
    })


@app.post("/api/memory/retrieval_probe")
async def memory_retrieval_probe(req: dict):
    """执行只读编辑器检索探针，策略只能由当前 YAML mode policy 决定。"""
    services = _services()
    request = RetrievalRequest(
        npc_id=str(req.get("npc_id", "")),
        conversation_participant_ids=[str(item) for item in req.get("conversation_participant_ids", []) if item],
        query_text=str(req.get("query_text", "")),
        conversation_summary=str(req.get("conversation_summary", "")),
        recent_turns=list(req.get("recent_turns", [])),
        location_id=str(req.get("location_id", "")),
        game_time=str(req.get("game_time", "")),
        mode=str(req.get("mode", "player_dialogue")),
    )
    try:
        result = services.retrieval.probe(request)
    except (KeyError, ValueError) as error:
        return JSONResponse({"success": False, "failure_reason": str(error)}, status_code=400)
    return JSONResponse({"success": True, "retrieval_trace_id": result.diagnostics.get("retrieval_trace_id", ""), "failure_reason": result.diagnostics.get("failure_reason", "")})


@app.get("/api/poll")
async def poll_messages():
    """Unity 轮询：返回当前所有积压消息。"""
    return JSONResponse({"messages": runtime.poll_messages()})


@app.post("/api/ws")
async def rest_bridge(req: dict):
    """HTTP POST 桥接: 接收 JSON → 处理 → 返回响应 JSON。"""
    responses = []

    class FakeWS:
        async def send_json(self, data):
            responses.append(data)

    fake_ws = FakeWS()
    try:
        await runtime.handle_message(fake_ws, req)
    except Exception as e:
        responses.append({"type": "GAME_ERROR", "message": str(e)})

    return JSONResponse({"responses": responses})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    protocol_session = ProtocolSession()
    runtime.message_bus.attach(ws)
    logger.info("Unity 已连接")

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "GAME_ERROR", "message": "Invalid JSON"})
                continue

            try:
                decoded = protocol_session.accept(msg)
                await runtime.handle_protocol_message(ws, decoded, protocol_session)
            except ProtocolDecodeError as error:
                await ws.send_json(protocol_session.response(
                    "protocol_error",
                    {},
                    str(msg.get("request_id") or ""),
                    error.error,
                ))
    except WebSocketDisconnect:
        logger.info("Unity 已断开")
        runtime.message_bus.detach(ws)
    except Exception as e:
        logger.error(f"WS 错误: {e}")
        runtime.message_bus.detach(ws)
