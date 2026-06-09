"""主程序入口。

三合一：分钟行情 + 持仓监控 + 大盘指数，同时运行。
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

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


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def position_monitor(settings) -> None:
    """持仓监控线程。"""

    from position.monitor import build_position_message

    binance_client = BinanceClient(
        settings.binance_base_url,
        settings.request_timeout,
        api_key=settings.binance_api_key,
        api_secret=settings.binance_api_secret,
    )
    feishu_bot = FeishuBot(settings.feishu_webhook, settings.request_timeout)
    interval = 120  # 2 分钟
    logging.info("持仓监控线程启动，每 %d 秒推送一次", interval)

    while True:
        time.sleep(interval)
        try:
            positions = binance_client.fetch_open_positions()
            if not positions:
                logging.info("持仓监控：当前没有合约持仓，跳过本轮")
                continue
            minute_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            message = build_position_message(positions, minute_text)
            feishu_bot.send_text(message)
            logging.info("持仓监控：飞书推送成功，共 %d 个持仓", len(positions))
        except Exception:  # noqa: BLE001
            logging.exception("持仓监控：本轮查询或推送失败")


def market_index_monitor(settings) -> None:
    """大盘指数监控线程。"""

    from index.data import INDEX_MAP, build_index_message, fetch_index_data

    index_feishu_bot = FeishuBot(settings.feishu_index_webhook, settings.request_timeout)
    tickers = list(INDEX_MAP.keys())
    interval = 120  # 2 分钟
    logging.info("大盘指数线程启动，每 %d 秒推送一次", interval)

    while True:
        time.sleep(interval)
        try:
            data = fetch_index_data(tickers)
            if not data:
                logging.info("大盘指数：本轮无有效数据，跳过")
                continue
            minute_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            message = build_index_message(data, minute_text)
            index_feishu_bot.send_text(message)
            logging.info("大盘指数：飞书推送成功，共 %d 个指数", len(data))
        except Exception:  # noqa: BLE001
            logging.exception("大盘指数：本轮查询或推送失败")


def main() -> None:
    """启动三合一监控。"""

    setup_logging()
    settings = load_settings()
    binance_client = BinanceClient(settings.binance_base_url, settings.request_timeout)
    feishu_bot = FeishuBot(settings.feishu_price_webhook, settings.request_timeout)
    invalid_symbols: set[str] = set()

    logging.info("监控启动，当前关注币对: %s", ", ".join(settings.symbols))

    # 启动持仓监控线程
    threading.Thread(target=position_monitor, args=(settings,), daemon=True).start()

    # 启动大盘指数监控线程
    threading.Thread(target=market_index_monitor, args=(settings,), daemon=True).start()

    # 主线程：分钟行情监控
    while True:
        sleep_until_next_round(settings.send_delay_seconds)
        minute_start = get_current_minute_start(settings.send_delay_seconds)
        message_lines: list[str] = []

        for symbol in settings.symbols:
            if symbol in invalid_symbols:
                continue
            try:
                ticker = binance_client.fetch_previous_minute_ticker(symbol, minute_start)
                message_lines.append(format_line(ticker))
            except Exception as exc:  # noqa: BLE001
                if "Invalid symbol" in str(exc):
                    invalid_symbols.add(symbol)
                    logging.warning("币对 %s 在当前币安接口不可用，后续轮次将自动跳过", symbol)
                    continue
                logging.warning("拉取 %s 行情失败: %s", symbol, exc)
                message_lines.append(format_error_line(symbol))

        if not message_lines:
            logging.warning("本轮没有可发送的有效行情，跳过飞书推送")
            continue

        message = build_message(minute_start - timedelta(minutes=1), message_lines)

        try:
            feishu_bot.send_text(message)
            logging.info("飞书消息发送成功")
        except Exception:  # noqa: BLE001
            logging.exception("飞书消息发送失败")


if __name__ == "__main__":
    main()
