"""项目配置读取。

优先从项目根目录 `.env` 文件读取配置，未配置时再回退到系统环境变量。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """封装运行配置，避免在业务代码里直接读取环境变量。"""

    binance_base_url: str
    binance_api_key: str
    binance_api_secret: str
    feishu_webhook: str
    symbols: list[str]
    request_timeout: int
    send_delay_seconds: int


def load_project_env() -> dict[str, str]:
    """读取项目内 `.env` 文件。

    这里只做当前项目需要的简单解析，支持 `KEY=VALUE` 形式。
    """

    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return {}

    env_map: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        env_map[key.strip()] = value.strip().strip("'").strip('"')

    return env_map


def load_settings() -> Settings:
    """读取并校验运行配置。"""

    env_map = load_project_env()

    # 关键业务逻辑：优先读项目内 `.env`，这样部署和本地运行都不需要额外 export。
    raw_symbols = env_map.get(
        "SYMBOLS",
        os.getenv(
            "SYMBOLS",
            "BTCUSDT,ETHUSDT,MRVLUSDT,MUUSDT,SNDKUSDT,ARMUSDT,NOKUSDT,FLNCUSDT",
        ),
    )
    symbols = [item.strip().upper() for item in raw_symbols.split(",") if item.strip()]
    feishu_webhook = env_map.get(
        "FEISHU_WEBHOOK",
        os.getenv(
            "FEISHU_WEBHOOK",
            "https://open.feishu.cn/open-apis/bot/v2/hook/b0473838-6d18-4ac5-b5fa-3be8c6a11e5b",
        ),
    ).strip()
    binance_api_key = env_map.get("BINANCE_API_KEY", os.getenv("BINANCE_API_KEY", "")).strip()
    binance_api_secret = env_map.get(
        "BINANCE_API_SECRET",
        os.getenv("BINANCE_API_SECRET", ""),
    ).strip()

    return Settings(
        binance_base_url=env_map.get(
            "BINANCE_BASE_URL",
            os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com"),
        ).rstrip("/"),
        binance_api_key=binance_api_key,
        binance_api_secret=binance_api_secret,
        feishu_webhook=feishu_webhook,
        symbols=symbols,
        request_timeout=int(env_map.get("REQUEST_TIMEOUT", os.getenv("REQUEST_TIMEOUT", "10"))),
        send_delay_seconds=int(
            env_map.get("SEND_DELAY_SECONDS", os.getenv("SEND_DELAY_SECONDS", "2"))
        ),
    )
