"""
全局配置加载。读取 settings.yaml + 环境变量 + shared/ JSON。
"""
import os
import json
import yaml
from pathlib import Path
from dataclasses import dataclass, field

ROOT_DIR = Path(__file__).resolve().parent.parent
SHARED_DIR = ROOT_DIR.parent / "shared"
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
SAVE_DIR = ROOT_DIR.parent / "SaveData"


@dataclass
class Config:
    """应用全局配置"""
    # 服务器
    host: str = "127.0.0.1"
    ws_port: int = 8765
    rest_port: int = 8766

    # LLM
    llm_provider: str = "anthropic"  # anthropic | openai
    llm_model: str = "claude-sonnet-4-6"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_thinking_mode: str = ""

    # 本地模型
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    embedding_device: str = "cpu"  # cpu | cuda

    # 数据库
    sqlite_path: str = ""
    lancedb_path: str = ""

    # 游戏
    short_term_days: int = 7
    midnight_hour: int = 24

    # NPC 列表
    npc_ids: list = field(default_factory=lambda: ["sakura", "chihaya", "kazuha", "tatsunosuke", "kujo", "player"])

    # shared 目录加载的 JSON 配置
    locations: dict = field(default_factory=dict)
    actions: dict = field(default_factory=dict)
    items: list = field(default_factory=list)


def load_config() -> Config:
    """加载全部配置，返回 Config 实例"""
    cfg = Config()

    # 1. YAML 配置文件（强制 UTF-8，避免 Windows GBK 损坏数据）
    yaml_path = CONFIG_DIR / "settings.yaml"
    if yaml_path.exists():
        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f.read()) or {}
        _apply_yaml(cfg, yaml_data)

    # 2. 环境变量覆盖（优先 DEEPSEEK_API_KEY）
    cfg.llm_api_key = (os.getenv("DEEPSEEK_API_KEY") or
                       os.getenv("ANTHROPIC_API_KEY") or
                       os.getenv("OPENAI_API_KEY") or
                       cfg.llm_api_key)
    if os.getenv("LLM_MODEL"):
        cfg.llm_model = os.getenv("LLM_MODEL")
    if os.getenv("LLM_PROVIDER"):
        cfg.llm_provider = os.getenv("LLM_PROVIDER")

    # 3. 数据库路径
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cfg.sqlite_path = str(DATA_DIR / "game.db")
    cfg.lancedb_path = str(DATA_DIR / "lancedb")

    # 4. 加载 shared/ JSON 配置
    cfg.locations = _load_json(SHARED_DIR / "locations.json")
    cfg.actions = _load_json(SHARED_DIR / "actions.json")
    cfg.items = _load_json(SHARED_DIR / "items.json").get("items", [])

    return cfg


def _apply_yaml(cfg: Config, data: dict) -> None:
    """将 YAML 数据映射到 Config 字段"""
    server = data.get("server", {})
    cfg.host = server.get("host", cfg.host)
    cfg.ws_port = server.get("ws_port", cfg.ws_port)
    cfg.rest_port = server.get("rest_port", cfg.rest_port)

    llm = data.get("llm", {})
    cfg.llm_provider = llm.get("provider", cfg.llm_provider)
    cfg.llm_model = llm.get("model", cfg.llm_model)
    cfg.llm_api_key = llm.get("api_key", cfg.llm_api_key)
    cfg.llm_base_url = llm.get("base_url", cfg.llm_base_url)
    cfg.llm_thinking_mode = str(
        llm.get("thinking_mode", cfg.llm_thinking_mode)
    ).strip()

    emb = data.get("embedding", {})
    cfg.embedding_model = emb.get("model", cfg.embedding_model)
    cfg.embedding_device = emb.get("device", cfg.embedding_device)

    game = data.get("game", {})
    cfg.short_term_days = game.get("short_term_days", cfg.short_term_days)
    cfg.midnight_hour = game.get("midnight_hour", cfg.midnight_hour)


def _load_json(path: Path) -> dict:
    """加载 JSON 文件，不存在则返回空"""
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# 全局单例
config: Config = None  # type: ignore


def init_config() -> Config:
    """初始化全局配置（启动时调用一次）"""
    global config
    config = load_config()
    return config
