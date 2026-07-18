"""
UTF-8 长跑压测脚本。

特点：
1. 直接写 UTF-8 日志和摘要，不依赖控制台 Tee
2. 使用隔离测试库与隔离 LanceDB 目录
3. 默认按 7 天口径推进，也支持自定义游戏分钟数或墙钟时长做 smoke / 长测
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
DOCS_DIR = ROOT_DIR / "docs" / "AIChanges"
ARTIFACTS_DIR = DOCS_DIR / "artifacts"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src import config as cfg_module
from src.application.runtime import GameRuntime
from src.world.clock import game_clock


NPC_IDS = ["sakura", "chihaya", "kazuha", "tatsunosuke", "kujo"]
RETRIEVAL_PAIRS = [
    ("sakura", "chihaya", "flower_shop.doorway"),
    ("chihaya", "sakura", "flower_shop.doorway"),
    ("kazuha", "tatsunosuke", "bookstore.doorway"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 UTF-8 7 天长跑压测。")
    parser.add_argument(
        "--tag",
        required=True,
        help="输出文件前缀，例如 2026-07-10_7day_full_test_utf8",
    )
    parser.add_argument(
        "--minutes",
        type=int,
        default=None,
        help="推进的游戏分钟数；未设置 --wall-minutes 时默认 7*1440。",
    )
    parser.add_argument(
        "--wall-minutes",
        type=float,
        default=None,
        help="按真实时间运行的分钟数；到点后在当前 tick 后优雅写 summary。",
    )
    parser.add_argument(
        "--player-location",
        default="player_cafe.doorway",
        help="压测时写入 game_state 的玩家位置；放到 street.crossroad 可看到更多 NPC 气泡。",
    )
    return parser.parse_args()


def configure_utf8_logging(log_path: Path) -> logging.Logger:
    """统一把压测日志直接写入 UTF-8 文件。"""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("SAKURA_ENABLE_POLL_QUEUE", "0")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    log_path.parent.mkdir(parents=True, exist_ok=True)

    stream_handler = logging.StreamHandler(sys.stdout)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[stream_handler, file_handler],
        force=True,
    )
    return logging.getLogger("sakurabashi.benchmark")


def graph_counts(sqlite) -> dict[str, dict[str, int]]:
    """统计各 NPC 当前图规模。"""
    result: dict[str, dict[str, int]] = {}
    for npc_id in NPC_IDS:
        nodes = sqlite.fetchone(
            "SELECT COUNT(*) AS cnt FROM memory_nodes WHERE subject_id = ?",
            (npc_id,),
        )["cnt"]
        edges = sqlite.fetchone(
            """SELECT COUNT(*) AS cnt
               FROM memory_edges
               WHERE node_a IN (SELECT id FROM memory_nodes WHERE subject_id = ?)
                  OR node_b IN (SELECT id FROM memory_nodes WHERE subject_id = ?)""",
            (npc_id, npc_id),
        )["cnt"]
        result[npc_id] = {"nodes": nodes, "edges": edges}
    return result


def short_term_counts(sqlite) -> list[dict]:
    """统计各 NPC 短期记忆数量。"""
    return sqlite.fetchall(
        """SELECT subject_id, COUNT(*) AS cnt
           FROM short_term_memories
           GROUP BY subject_id
           ORDER BY CASE subject_id
               WHEN 'sakura' THEN 1
               WHEN 'chihaya' THEN 2
               WHEN 'kazuha' THEN 3
               WHEN 'tatsunosuke' THEN 4
               WHEN 'kujo' THEN 5
               ELSE 99 END"""
    )


def edge_types(sqlite) -> list[dict]:
    """统计边类型分布。"""
    return sqlite.fetchall(
        """SELECT type, COUNT(*) AS cnt
           FROM memory_edges
           GROUP BY type
           ORDER BY cnt DESC, type ASC"""
    )


def latest_memories(sqlite, limit: int = 12) -> list[dict]:
    """获取最近写入的短期记忆片段。"""
    return sqlite.fetchall(
        """SELECT subject_id, created_at_game_time, substr(content, 1, 140) AS preview
           FROM short_term_memories
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,),
    )


def retrieval_metrics(sqlite) -> dict:
    """聚合检索诊断指标，观察图路由、LLM 路由和融合命中情况。"""
    totals = sqlite.fetchone(
        """SELECT COUNT(*) AS cnt,
                  COALESCE(SUM(vector_fallback), 0) AS vector_fallback,
                  COALESCE(SUM(llm_route_calls), 0) AS llm_route_calls,
                  COALESCE(SUM(local_route_skips), 0) AS local_route_skips,
                  COALESCE(SUM(hit_merged_count), 0) AS hit_merged_count,
                  COALESCE(AVG(elapsed_sec), 0.0) AS avg_elapsed_sec
           FROM memory_retrieval_logs"""
    ) or {}
    by_mode = sqlite.fetchall(
        """SELECT mode, COUNT(*) AS cnt,
                  COALESCE(SUM(vector_fallback), 0) AS vector_fallback,
                  COALESCE(SUM(llm_route_calls), 0) AS llm_route_calls,
                  COALESCE(SUM(local_route_skips), 0) AS local_route_skips,
                  COALESCE(SUM(hit_merged_count), 0) AS hit_merged_count,
                  COALESCE(AVG(elapsed_sec), 0.0) AS avg_elapsed_sec
           FROM memory_retrieval_logs
           GROUP BY mode
           ORDER BY cnt DESC"""
    )
    return {"total": totals, "by_mode": by_mode}


async def run_benchmark(
    minutes: int,
    tag: str,
    logger: logging.Logger,
    max_runtime_sec: float | None = None,
    player_location: str = "player_cafe.doorway",
) -> dict:
    """执行压测并返回摘要。"""
    artifact_root = ARTIFACTS_DIR / tag
    summary_path = artifact_root / f"{tag}_summary.json"

    if summary_path.exists():
        summary_path.unlink()

    cfg_module.DATA_DIR = artifact_root / "data"
    cfg_module.SAVE_DIR = artifact_root / "SaveData"
    cfg_module.DATA_DIR.mkdir(parents=True, exist_ok=True)
    cfg_module.SAVE_DIR.mkdir(parents=True, exist_ok=True)

    runtime = GameRuntime()
    await runtime.start()
    services = runtime.require_services()
    services.state_mgr.cold_start()
    game_clock.set_state(1, 8, 0, "sunny")
    services.sqlite.execute(
        "UPDATE game_state SET player_location = ?, updated_at = datetime('now') WHERE id = 1",
        (player_location,),
    )
    logger.info("压测玩家位置 player_location=%s", player_location)

    midnight_stats: list[dict] = []
    started = time.perf_counter()
    completed_game_minutes = 0
    stop_reason = "game_minutes_completed"

    try:
        await services.behavior.tick()

        while completed_game_minutes < minutes:
            if (
                max_runtime_sec is not None
                and completed_game_minutes > 0
                and time.perf_counter() - started >= max_runtime_sec
            ):
                stop_reason = "wall_time_reached"
                break

            if completed_game_minutes > 0 and completed_game_minutes % 720 == 0:
                logger.info(
                    "压测进度 minute=%s/%s time=%s runtime_sec=%.2f",
                    completed_game_minutes,
                    minutes,
                    game_clock.time_str(),
                    time.perf_counter() - started,
                )

            game_clock.minute += 1
            if game_clock.minute >= 60:
                game_clock.minute = 0
                game_clock.hour += 1

                if game_clock.hour == 24 and game_clock.minute == 0:
                    before_counts = graph_counts(services.sqlite)
                    before_stm = short_term_counts(services.sqlite)
                    midnight_started = time.perf_counter()
                    logger.info("午夜开始 day=%s time=%s", game_clock.day, game_clock.time_str())
                    await runtime.on_midnight()
                    duration_sec = round(time.perf_counter() - midnight_started, 2)
                    after_counts = graph_counts(services.sqlite)
                    after_stm = short_term_counts(services.sqlite)
                    midnight_stats.append(
                        {
                            "day": game_clock.day,
                            "duration_sec": duration_sec,
                            "before_counts": before_counts,
                            "after_counts": after_counts,
                            "before_stm": before_stm,
                            "after_stm": after_stm,
                        }
                    )
                    logger.info("午夜完成 day=%s duration_sec=%.2f", game_clock.day, duration_sec)

                if game_clock.hour >= 25:
                    game_clock.hour = 6
                    game_clock.day += 1
                    if getattr(game_clock, "_wake_pending", False):
                        await runtime.on_wake()
                        game_clock._wake_pending = False

            await services.behavior.tick()
            completed_game_minutes += 1

        retrieval_samples = []
        for owner, target, location in RETRIEVAL_PAIRS:
            try:
                text = services.retrieval.retrieve(owner, target, location, game_clock.time_str())
            except Exception as exc:
                text = f"[retrieve failed] {exc}"
            retrieval_samples.append({"owner": owner, "target": target, "text": text})

        summary = {
            "runtime_sec": round(time.perf_counter() - started, 2),
            "requested_game_minutes": minutes,
            "completed_game_minutes": completed_game_minutes,
            "max_runtime_sec": max_runtime_sec,
            "stop_reason": stop_reason,
            "player_location": player_location,
            "final_game_time": game_clock.time_str(),
            "midnight_stats": midnight_stats,
            "graph_counts": graph_counts(services.sqlite),
            "short_term_by_subject": short_term_counts(services.sqlite),
            "edge_types": edge_types(services.sqlite),
            "latest_memories": latest_memories(services.sqlite),
            "retrieval_metrics": retrieval_metrics(services.sqlite),
            "retrieval_samples": retrieval_samples,
        }

        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info("SUMMARY_JSON=%s", json.dumps(summary, ensure_ascii=False))
        return summary
    finally:
        await runtime.stop()


def main() -> None:
    args = parse_args()
    artifact_root = ARTIFACTS_DIR / args.tag
    if artifact_root.exists():
        shutil.rmtree(artifact_root)

    log_path = ARTIFACTS_DIR / args.tag / f"{args.tag}.log"
    logger = configure_utf8_logging(log_path)
    max_runtime_sec = args.wall_minutes * 60 if args.wall_minutes is not None else None
    game_minutes = args.minutes
    if game_minutes is None:
        game_minutes = 10**9 if max_runtime_sec is not None else 7 * 1440
    logger.info(
        "开始 UTF-8 长跑压测 tag=%s minutes=%s wall_minutes=%s",
        args.tag,
        game_minutes,
        args.wall_minutes,
    )
    summary = asyncio.run(
        run_benchmark(
            game_minutes,
            args.tag,
            logger,
            max_runtime_sec,
            player_location=args.player_location,
        )
    )
    logger.info(
        "压测结束 final_game_time=%s runtime_sec=%.2f stop_reason=%s completed_game_minutes=%s",
        summary["final_game_time"],
        summary["runtime_sec"],
        summary["stop_reason"],
        summary["completed_game_minutes"],
    )


if __name__ == "__main__":
    main()
