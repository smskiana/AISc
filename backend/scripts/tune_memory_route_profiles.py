"""使用真实记忆图和 LLM 二分搜索性能、平衡、质量三档路由阈值。"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import sys
import time
from collections import Counter
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.src import config as cfg_module
from backend.src.database.lancedb_client import LanceDBClient
from backend.src.database.sqlite_client import SQLiteClient
from backend.src.dialogue import llm_client as llm_module
from backend.src.memory.retrieval import RETRIEVAL_MODE_CONFIGS, RetrievalEngine


PROFILE_TARGETS = {
    "performance": {"display_name": "性能", "quality_floor": 0.75},
    "balanced": {"display_name": "平衡", "quality_floor": 0.95},
    "quality": {"display_name": "质量", "quality_floor": 1.00, "always_llm": True},
}
STRICT_THRESHOLDS = {"min_score": 3.0, "margin": 1.0}
PERMISSIVE_THRESHOLDS = {"min_score": 0.0, "margin": 0.0}
NPC_IDS = ["sakura", "chihaya", "kazuha", "tatsunosuke", "kujo"]


def parse_args() -> argparse.Namespace:
    """解析真实 LLM 路由调参参数。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-repeats", type=int, default=3)
    parser.add_argument("--max-samples-per-mode", type=int, default=8)
    parser.add_argument("--binary-iterations", type=int, default=18)
    parser.add_argument("--source-db", type=Path, default=ROOT_DIR / "backend" / "data" / "game.db")
    parser.add_argument("--source-lancedb", type=Path, default=ROOT_DIR / "backend" / "data" / "lancedb")
    parser.add_argument("--game-time", default="第7天 14:00")
    parser.add_argument("--player-location", default="street.crossroad")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "docs" / "AIChanges" / "artifacts" / "memory_route_profiles",
    )
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    """计算文件哈希，用于证明正式数据库没有被测试修改。"""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def thresholds_for_aggressiveness(aggressiveness: float) -> dict[str, float]:
    """把单调激进度映射为本地路由最低分和领先差阈值。"""
    value = min(max(float(aggressiveness), 0.0), 1.0)
    return {
        "min_score": round(
            STRICT_THRESHOLDS["min_score"]
            + (PERMISSIVE_THRESHOLDS["min_score"] - STRICT_THRESHOLDS["min_score"]) * value,
            6,
        ),
        "margin": round(
            STRICT_THRESHOLDS["margin"]
            + (PERMISSIVE_THRESHOLDS["margin"] - STRICT_THRESHOLDS["margin"]) * value,
            6,
        ),
    }


def selection_overlap(selected: list[str], baseline: list[str]) -> float:
    """计算本地选边对稳定 LLM 基线的召回比例。"""
    if not baseline:
        return 1.0 if not selected else 0.0
    return len(set(selected) & set(baseline)) / len(set(baseline))


def should_use_local(sample: dict, thresholds: dict[str, float]) -> bool:
    """按候选分数和指定阈值判断该样本是否由本地路由接管。"""
    max_select = int(sample["max_select"])
    scores = sample["scores"]
    if len(scores) <= max_select:
        return True
    floor = float(scores[max_select - 1])
    margin = floor - float(scores[max_select])
    return floor >= thresholds["min_score"] and margin >= thresholds["margin"]


def evaluate_thresholds(samples: list[dict], thresholds: dict[str, float]) -> dict:
    """计算指定阈值相对始终调用 LLM 基线的效果和性能指标。"""
    if not samples:
        return {
            "sample_count": 0,
            "quality_retention": 0.0,
            "local_takeovers": 0,
            "llm_calls": 0,
            "llm_savings_rate": 0.0,
            "local_overlap": 0.0,
        }

    quality_scores: list[float] = []
    local_scores: list[float] = []
    local_takeovers = 0
    for sample in samples:
        if should_use_local(sample, thresholds):
            local_takeovers += 1
            overlap = selection_overlap(sample["local_selection"], sample["baseline_selection"])
            quality_scores.append(overlap)
            local_scores.append(overlap)
        else:
            quality_scores.append(1.0)

    count = len(samples)
    return {
        "sample_count": count,
        "quality_retention": round(statistics.fmean(quality_scores), 6),
        "local_takeovers": local_takeovers,
        "llm_calls": count - local_takeovers,
        "llm_savings_rate": round(local_takeovers / count, 6),
        "local_overlap": round(statistics.fmean(local_scores), 6) if local_scores else 1.0,
    }


def binary_search_profile(
    samples: list[dict], quality_floor: float, iterations: int = 18
) -> dict:
    """二分搜索满足效果下限的最大本地路由激进度。"""
    low = 0.0
    high = 1.0
    best = 0.0
    for _ in range(iterations):
        midpoint = (low + high) / 2.0
        metrics = evaluate_thresholds(samples, thresholds_for_aggressiveness(midpoint))
        if metrics["quality_retention"] >= quality_floor:
            best = midpoint
            low = midpoint
        else:
            high = midpoint

    thresholds = thresholds_for_aggressiveness(best)
    return {
        "aggressiveness": round(best, 6),
        "thresholds": thresholds,
        **evaluate_thresholds(samples, thresholds),
    }


def copy_isolated_data(
    output_dir: Path, source_db: Path, source_lance: Path
) -> tuple[Path, Path, str]:
    """把指定 SQLite 与 LanceDB 数据源复制到本轮隔离目录。"""
    source_db = source_db.resolve()
    source_lance = source_lance.resolve()
    if not source_db.is_file():
        raise FileNotFoundError(f"SQLite 数据源不存在: {source_db}")
    isolated_dir = output_dir / "isolated_data"
    if isolated_dir.exists():
        shutil.rmtree(isolated_dir)
    isolated_dir.mkdir(parents=True, exist_ok=True)
    isolated_db = isolated_dir / "game.db"
    shutil.copy2(source_db, isolated_db)
    isolated_lance = isolated_dir / "lancedb"
    if source_lance.exists():
        shutil.copytree(source_lance, isolated_lance)
    return isolated_db, isolated_lance, file_sha256(source_db)


def scenario_signature(candidate_edges: list[dict], mode: str, max_select: int) -> str:
    """生成候选集合签名，避免同一套路由题重复调用 LLM。"""
    edge_ids = ",".join(str(edge.get("edge_id", "")) for edge in candidate_edges)
    return f"{mode}|{max_select}|{edge_ids}"


def collect_mode_samples(
    engine: RetrievalEngine,
    mode: str,
    max_samples: int,
    game_time: str,
    player_location: str,
) -> list[dict]:
    """从真实图采集首跳和潜在后续跳的多候选路由样本。"""
    config = RETRIEVAL_MODE_CONFIGS[mode]
    max_select = int(config["edges_per_route"])
    candidates_by_signature: dict[str, dict] = {}

    for owner in NPC_IDS:
        targets = ["player"] if mode == "player_dialogue" else [npc for npc in NPC_IDS if npc != owner]
        state = engine.db.fetchone(
            "SELECT current_location FROM npc_states WHERE npc_id=?", (owner,)
        ) or {}
        owner_location = str(state.get("current_location") or "street")
        for target in targets:
            location = player_location if mode == "player_dialogue" else owner_location
            route_context = engine._build_route_context(
                npc_id=owner,
                target_id=target,
                location="nightly_reflection" if mode == "nightly_impression" else location,
                game_time=game_time,
                config=config,
                mode=mode,
            )
            start_ids, target_start_id = engine._find_start_nodes(owner, target)
            frontiers = [start_ids] if start_ids else []
            node_rows = engine.db.fetchall(
                "SELECT id FROM memory_nodes WHERE subject_id=? ORDER BY id", (owner,)
            )
            frontiers.extend([[str(row["id"])] for row in node_rows])

            for frontier in frontiers:
                if not frontier:
                    continue
                edges = engine._collect_candidate_edges(
                    npc_id=owner,
                    target_id=target,
                    frontier=frontier,
                    target_start_id=target_start_id,
                    route_context=route_context,
                    visited_nodes=set(frontier),
                    visited_edges=set(),
                    max_edges_per_hop=int(config["max_edges_per_hop"]),
                )
                if len(edges) <= max_select:
                    continue
                signature = scenario_signature(edges, mode, max_select)
                candidates_by_signature.setdefault(
                    signature,
                    {
                        "id": f"{mode}_{len(candidates_by_signature) + 1:02d}",
                        "mode": mode,
                        "npc_id": owner,
                        "target_id": target,
                        "frontier": frontier,
                        "route_context": route_context,
                        "candidate_edges": edges,
                        "max_select": max_select,
                        "scores": [round(float(edge.get("local_score", 0.0)), 6) for edge in edges],
                        "local_selection": [str(edge["edge_id"]) for edge in edges[:max_select]],
                    },
                )

    # 同时保留分差小的难题和分差大的明确题，避免样本只偏向一种分布。
    samples = list(candidates_by_signature.values())
    samples.sort(
        key=lambda item: abs(
            item["scores"][item["max_select"] - 1] - item["scores"][item["max_select"]]
        )
    )
    hard_count = (max_samples + 1) // 2
    selected = samples[:hard_count]
    selected.extend(reversed(samples[hard_count:][-max(0, max_samples - len(selected)) :]))
    return selected[:max_samples]


def build_llm_baseline(
    engine: RetrievalEngine, sample: dict, repeats: int
) -> dict:
    """对同一路由样本重复调用 LLM，以多数选择形成稳定基线。"""
    selections: list[list[str]] = []
    latencies: list[float] = []
    context = dict(sample["route_context"])
    context["local_route_min_score"] = 999.0
    context["local_route_margin"] = 999.0

    for _ in range(repeats):
        context["_diagnostics"] = {"llm_route_calls": 0, "local_route_skips": 0}
        started = time.perf_counter()
        chosen = engine._route_edges_llm(
            route_context=context,
            frontier=sample["frontier"],
            candidate_edges=sample["candidate_edges"],
            max_select=sample["max_select"],
            hop_index=0,
            max_hops=int(RETRIEVAL_MODE_CONFIGS[sample["mode"]]["max_hops"]),
        )
        latencies.append(time.perf_counter() - started)
        selections.append([str(edge["edge_id"]) for edge in chosen])

    counts = Counter(edge_id for selection in selections for edge_id in selection)
    candidate_order = {
        str(edge["edge_id"]): index for index, edge in enumerate(sample["candidate_edges"])
    }
    consensus = sorted(
        counts,
        key=lambda edge_id: (-counts[edge_id], candidate_order.get(edge_id, 10**6)),
    )[: sample["max_select"]]
    pair_overlaps = [selection_overlap(selection, consensus) for selection in selections]
    return {
        "baseline_selection": consensus,
        "baseline_runs": selections,
        "baseline_stability": round(statistics.fmean(pair_overlaps), 6),
        "llm_latency_sec": [round(value, 6) for value in latencies],
    }


def serializable_sample(sample: dict) -> dict:
    """移除冗长内部上下文，仅保留可审计的样本信息。"""
    return {
        "id": sample["id"],
        "mode": sample["mode"],
        "npc_id": sample["npc_id"],
        "target_id": sample["target_id"],
        "frontier": sample["frontier"],
        "max_select": sample["max_select"],
        "scores": sample["scores"],
        "local_selection": sample["local_selection"],
        "baseline_selection": sample["baseline_selection"],
        "baseline_runs": sample["baseline_runs"],
        "baseline_stability": sample["baseline_stability"],
        "llm_latency_sec": sample["llm_latency_sec"],
        "candidates": [
            {
                "edge_id": edge.get("edge_id"),
                "node_id": edge.get("node_id"),
                "type": edge.get("type"),
                "edge_type": edge.get("edge_type"),
                "clarity": edge.get("clarity"),
                "local_score": edge.get("local_score"),
                "value": str(edge.get("value", ""))[:120],
            }
            for edge in sample["candidate_edges"]
        ],
    }


def build_markdown_report(result: dict) -> str:
    """把原始测试结果整理为玩家可直接选择的三档报告。"""
    lines = [
        "# 记忆路由三档二分测试结果",
        "",
        f"模型：`{result['llm']['provider']}/{result['llm']['model']}`",
        "",
        "效果保持率表示相对“每次都调用当前 LLM 路由”的选边保持程度。",
        "",
    ]
    for mode, mode_result in result["modes"].items():
        lines.extend(
            [
                f"## {mode}",
                "",
                f"有效样本：{mode_result['sample_count']}；LLM 基线平均稳定度：{mode_result['baseline_stability']:.1%}；平均调用延迟：{mode_result['avg_llm_latency_sec']:.3f}s。",
                "",
                "| 档位 | min_score | margin | 效果保持率 | LLM 节省率 | 预计平均路由延迟 |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for profile_key in ("performance", "balanced", "quality"):
            profile = mode_result["profiles"][profile_key]
            lines.append(
                f"| {PROFILE_TARGETS[profile_key]['display_name']} | "
                f"{profile['thresholds']['min_score']:.3f} | {profile['thresholds']['margin']:.3f} | "
                f"{profile['quality_retention']:.1%} | {profile['llm_savings_rate']:.1%} | "
                f"{profile['estimated_avg_route_latency_sec']:.3f}s |"
            )
        lines.append("")
    lines.extend(
        [
            "## 适用边界",
            "",
            "- 结论来自当前真实记忆图的小规模样本，不等同于永久阈值。",
            "- `player_dialogue` 或 `npc_dialogue` 样本不足时，应优先选择质量档。",
            "- 本轮不修改正式运行阈值，只输出可选择配置。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    """运行隔离采样、真实 LLM 基线和三档二分搜索。"""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    isolated_db, isolated_lance, source_hash_before = copy_isolated_data(
        args.output_dir,
        args.source_db,
        args.source_lancedb,
    )

    config = cfg_module.init_config()
    if not config.llm_api_key:
        raise RuntimeError("未配置 LLM API Key，无法建立真实 LLM 路由基线")
    llm_module.init_llm(
        config.llm_provider,
        config.llm_model,
        config.llm_api_key,
        config.llm_base_url,
    )
    db = SQLiteClient(str(isolated_db))
    lance = LanceDBClient(str(isolated_lance), config.npc_ids)
    engine = RetrievalEngine(db, lance)

    result = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "llm": {"provider": config.llm_provider, "model": config.llm_model},
        "settings": {
            "source_db": str(args.source_db.resolve()),
            "source_lancedb": str(args.source_lancedb.resolve()),
            "game_time": args.game_time,
            "player_location": args.player_location,
            "baseline_repeats": args.baseline_repeats,
            "max_samples_per_mode": args.max_samples_per_mode,
            "binary_iterations": args.binary_iterations,
            "profile_quality_floors": {
                key: value["quality_floor"] for key, value in PROFILE_TARGETS.items()
            },
        },
        "modes": {},
    }

    all_samples: list[dict] = []
    for mode in RETRIEVAL_MODE_CONFIGS:
        print(f"[route-tune] collecting mode={mode}", flush=True)
        samples = collect_mode_samples(
            engine,
            mode,
            args.max_samples_per_mode,
            args.game_time,
            args.player_location,
        )
        for index, sample in enumerate(samples, start=1):
            print(
                f"[route-tune] baseline mode={mode} sample={index}/{len(samples)} id={sample['id']}",
                flush=True,
            )
            sample.update(build_llm_baseline(engine, sample, args.baseline_repeats))

        latencies = [latency for sample in samples for latency in sample["llm_latency_sec"]]
        avg_latency = statistics.fmean(latencies) if latencies else 0.0
        profiles = {}
        for profile_key, profile_config in PROFILE_TARGETS.items():
            if profile_config.get("always_llm"):
                thresholds = {"min_score": 999.0, "margin": 999.0}
                profile = {
                    "aggressiveness": 0.0,
                    "thresholds": thresholds,
                    **evaluate_thresholds(samples, thresholds),
                }
            else:
                profile = binary_search_profile(
                    samples,
                    profile_config["quality_floor"],
                    iterations=args.binary_iterations,
                )
            profile["estimated_avg_route_latency_sec"] = round(
                avg_latency * (1.0 - profile["llm_savings_rate"]), 6
            )
            profiles[profile_key] = profile

        result["modes"][mode] = {
            "sample_count": len(samples),
            "baseline_stability": round(
                statistics.fmean(sample["baseline_stability"] for sample in samples), 6
            )
            if samples
            else 0.0,
            "avg_llm_latency_sec": round(avg_latency, 6),
            "profiles": profiles,
        }
        all_samples.extend(serializable_sample(sample) for sample in samples)

    result["source_database_unchanged"] = (
        source_hash_before == file_sha256(args.source_db.resolve())
    )
    result["samples"] = all_samples
    json_path = args.output_dir / "memory_route_profiles.json"
    markdown_path = args.output_dir / "memory_route_profiles.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(build_markdown_report(result), encoding="utf-8")
    print(f"[route-tune] result={json_path}", flush=True)
    print(f"[route-tune] report={markdown_path}", flush=True)


if __name__ == "__main__":
    main()
