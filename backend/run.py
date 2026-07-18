"""
樱桥通 Python 后端入口。
启动 FastAPI (REST) + WebSocket 双端口。
"""
import os
import sys
import logging
import uvicorn
from pathlib import Path

# 确保 src 在 Python path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

def _configure_logging() -> None:
    """统一后端日志输出为 UTF-8，并同时落盘。"""
    os.environ.setdefault("PYTHONUTF8", "1")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    stream_handler = logging.StreamHandler(sys.stdout)
    file_handler = logging.FileHandler(log_dir / "backend.log", encoding="utf-8")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[stream_handler, file_handler],
        force=True,
    )


_configure_logging()


def main():
    from src.config import load_config
    cfg = load_config()

    logging.getLogger("sakurabashi").info(
        f"启动服务器: REST={cfg.rest_port} WS={cfg.ws_port}"
    )

    uvicorn.run(
        "src.main:app",
        host=cfg.host,
        port=cfg.rest_port,
        ws_max_size=1024 * 1024,  # 1MB
        log_level="warning",  # 抑制 GET /api/poll 等请求日志
    )


if __name__ == "__main__":
    main()
