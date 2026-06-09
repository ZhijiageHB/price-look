"""自选币种分钟行情监控（独立运行）。

每分钟推送关注币对的涨跌到飞书。
"""

from __future__ import annotations

import logging
import sys
from datetime import timedelta

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from binance_client import BinanceClient
from config import load_settings
from feishu_bot import FeishuBot
from price.formatter import (
    build_message,
    format_error_line,
    format_line,
    get_current_minute_start,
    sleep_until_next_round,
)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    settings = load_settings()
    client = BinanceClient(settings.binance_base_url, settings.request_timeout)
    feishu_bot = FeishuBot(settings.feishu_price_webhook, settings.request_timeout)
    invalid_symbols: set[str] = set()

    logging.info("分钟行情监控启动，关注币对: %s", ", ".join(settings.symbols))

    while True:
        sleep_until_next_round(settings.send_delay_seconds)
        minute_start = get_current_minute_start(settings.send_delay_seconds)
        lines: list[str] = []

        for symbol in settings.symbols:
            if symbol in invalid_symbols:
                continue
            try:
                ticker = client.fetch_previous_minute_ticker(symbol, minute_start)
                lines.append(format_line(ticker))
            except Exception as exc:  # noqa: BLE001
                if "Invalid symbol" in str(exc):
                    invalid_symbols.add(symbol)
                    continue
                lines.append(format_error_line(symbol))

        if not lines:
            continue

        message = build_message(minute_start - timedelta(minutes=1), lines)

        try:
            feishu_bot.send_text(message)
            logging.info("飞书推送成功")
        except Exception:  # noqa: BLE001
            logging.exception("飞书推送失败")


if __name__ == "__main__":
    main()
