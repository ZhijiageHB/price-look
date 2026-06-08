"""主程序入口。

每分钟对关注币对查询上一分钟 K 线，并把结果汇总后发送到飞书。
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from binance_client import BinanceClient, MinuteTicker
from config import load_settings
from feishu_bot import FeishuBot


def setup_logging() -> None:
    """初始化日志，方便观察轮询和错误信息。"""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def get_current_minute_start(send_delay_seconds: int) -> datetime:
    """基于发送延迟推导当前整分钟开始时间。

    例如 10:01:02 发送时，这里会得到 10:01:00，然后去查询 10:00:00-10:00:59 的 K 线。
    """

    now = time.time() - send_delay_seconds
    current_minute_epoch = int(now // 60) * 60
    return datetime.fromtimestamp(current_minute_epoch, tz=timezone.utc)


def sleep_until_next_round(send_delay_seconds: int) -> None:
    """睡眠到下一个整分钟后的固定偏移点，保证每分钟只发送一次。"""

    now = time.time()
    next_run = ((int(now) // 60) + 1) * 60 + send_delay_seconds
    sleep_seconds = max(0.0, next_run - now)
    time.sleep(sleep_seconds)


def format_line(ticker: MinuteTicker) -> str:
    """把单个币对转换成用户要求的一行文本。"""

    line = (
        f"{ticker.symbol} 现价：{ticker.close_price:.8f}".rstrip("0").rstrip(".")
        + f" 开盘：{ticker.open_price:.8f}".rstrip("0").rstrip(".")
        + f" 收盘：{ticker.close_price:.8f}".rstrip("0").rstrip(".")
        + f" 振幅：{ticker.change_pct:+.2f}%"
    )
    # 关键业务逻辑：当分钟振幅绝对值超过 0.2% 时，按涨跌方向追加不同颜色的预警符号。
    if abs(ticker.change_pct) > 0.2:
        line += " 🟢" if ticker.change_pct > 0 else " 🔴"
    return line


def format_error_line(symbol: str, error: Exception) -> str:
    """把异常压缩成单行，避免飞书消息过长。"""

    _ = error
    return f"{symbol} 现价：N/A 振幅：N/A"


def build_message(minute_start: datetime, lines: list[str]) -> str:
    """组装最终发送到飞书的纯文本内容。"""

    minute_text = minute_start.astimezone().strftime("%Y-%m-%d %H:%M")
    return "\n".join([f"币安永续分钟行情 {minute_text}", *lines])


def position_monitor(settings, feishu_bot: FeishuBot) -> None:
    """持仓监控线程，每五分钟查询并推送到飞书。"""

    binance_client = BinanceClient(
        settings.binance_base_url,
        settings.request_timeout,
        api_key=settings.binance_api_key,
        api_secret=settings.binance_api_secret,
    )
    interval = 120  # 2 分钟
    logging.info("持仓监控线程启动，每 %d 秒推送一次", interval)

    while True:
        time.sleep(interval)
        try:
            from account_positions import build_position_message

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


def main() -> None:
    """启动分钟监控循环。"""

    setup_logging()
    settings = load_settings()
    binance_client = BinanceClient(settings.binance_base_url, settings.request_timeout)
    feishu_bot = FeishuBot(settings.feishu_webhook, settings.request_timeout)
    invalid_symbols: set[str] = set()

    logging.info("监控启动，当前关注币对: %s", ", ".join(settings.symbols))

    # 启动持仓监控线程，每五分钟推送一次
    pos_thread = threading.Thread(
        target=position_monitor, args=(settings, feishu_bot), daemon=True
    )
    pos_thread.start()

    while True:
        sleep_until_next_round(settings.send_delay_seconds)
        current_minute_start = get_current_minute_start(settings.send_delay_seconds)
        message_lines: list[str] = []

        # 关键业务逻辑：每个币对都独立请求上一分钟 K 线，单个失败不影响整批发送。
        # 如果某个币对在当前接口下明确是无效 symbol，则后续轮次直接跳过，避免日志持续刷屏。
        for symbol in settings.symbols:
            if symbol in invalid_symbols:
                continue

            try:
                ticker = binance_client.fetch_previous_minute_ticker(symbol, current_minute_start)
                message_lines.append(format_line(ticker))
            except Exception as exc:  # noqa: BLE001
                if "Invalid symbol" in str(exc):
                    invalid_symbols.add(symbol)
                    logging.warning("币对 %s 在当前币安接口不可用，后续轮次将自动跳过", symbol)
                    continue

                logging.warning("拉取 %s 行情失败: %s", symbol, exc)
                message_lines.append(format_error_line(symbol, exc))

        if not message_lines:
            logging.warning("本轮没有可发送的有效行情，跳过飞书推送")
            continue

        # 关键业务逻辑：本轮发送的是“上一分钟”的 K 线，因此标题分钟也要对应上一分钟。
        message = build_message(current_minute_start - timedelta(minutes=1), message_lines)

        try:
            feishu_bot.send_text(message)
            logging.info("飞书消息发送成功")
        except Exception:  # noqa: BLE001
            logging.exception("飞书消息发送失败")


if __name__ == "__main__":
    main()
