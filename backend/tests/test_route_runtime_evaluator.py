"""隔离运行时检索评估入口测试。"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from backend.scripts import evaluate_route_runtime as evaluator


def test_factory_requires_explicit_isolation_declaration(monkeypatch) -> None:
    """普通 module:function 不得绕过隔离声明。"""
    monkeypatch.setattr(evaluator.importlib, "import_module", lambda name: SimpleNamespace(factory=lambda: object()))
    with pytest.raises(ValueError, match="missing_isolation"):
        evaluator._load_factory("fixture:factory")


def test_corpus_requires_isolation_and_permission_expectations(tmp_path) -> None:
    """缺逐条隔离或允许/拒绝节点预期的 corpus 必须拒绝。"""
    path = tmp_path / "corpus.jsonl"
    path.write_text(json.dumps({"request": {"npc_id": "sakura"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing_isolation_or_permissions"):
        evaluator._read_corpus(path)


def test_evaluate_calls_probe_and_writes_safe_counts(tmp_path, monkeypatch) -> None:
    """评估只调用 probe，并汇总命中和越权节点。"""
    probes: list[object] = []
    class _Engine:
        """返回固定隔离检索结果。"""
        def probe(self, request):
            probes.append(request)
            return SimpleNamespace(retrieved_node_ids=["allowed"], diagnostics={"direction_provider_requested": "r3_v2", "direction_provider_adopted": "r3_v2", "direction_model_call_count": 1, "vector_query_count": 1, "llm_route_calls": 0})
    monkeypatch.setattr(evaluator, "_load_factory", lambda spec: lambda provider_id: _Engine())
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps({"case_id": "one", "isolated_data": True, "request": {"npc_id": "sakura"}, "expected_node_ids": ["allowed"], "forbidden_node_ids": ["secret"]}), encoding="utf-8")
    output = tmp_path / "report.json"
    summary = evaluator.evaluate("fixture:factory", corpus, output, "local")
    assert len(probes) == 1
    assert summary["case_count"] == 1
    assert summary["expected_hit_rate"] == 1.0
    assert summary["forbidden_hit_count"] == 0
    assert summary["side_effect_free"] is True
    assert output.is_file()


def test_bundled_isolated_factory_and_corpus_run_local(tmp_path) -> None:
    """提交的真实 SQLite/LanceDB 夹具能验证 local 命中、权限和无副作用。"""
    corpus = Path(__file__).with_name("fixtures") / "route_runtime_corpus.jsonl"
    summary = evaluator.evaluate("backend.tests.route_runtime_isolated_factory:create_engine", corpus, tmp_path / "local.json", "local")
    assert summary["case_count"] == 2
    assert summary["expected_hit_rate"] == 1.0
    assert summary["forbidden_hit_count"] == 0
    assert summary["adopted_provider_count"] == 0
    assert summary["side_effect_free"] is True


def test_cli_help_runs_from_repo_root() -> None:
    """脚本按文件路径启动时仍能导入 backend 包。"""
    root = Path(__file__).parents[2]
    result = subprocess.run([sys.executable, "backend/scripts/evaluate_route_runtime.py", "--help"], cwd=root, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert "--provider" in result.stdout
