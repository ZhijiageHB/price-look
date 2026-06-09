"""分钟行情格式化工具。"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from binance_client import MinuteTicker


def format_line(ticker: MinuteTicker) -> str:
    """把单个币对转换成一行文本。"""

    line = (
        f"{ticker.symbol} 现价：{ticker.close_price:.2f}"
        + f" 开盘：{ticker.open_price:.2f}"
        + f" 收盘：{ticker.close_price:.2f}"
        + f" 振幅：{ticker.change_pct:+.2f}%"
    )
    if abs(ticker.change_pct) > 0.2:
        line += " 🟢" if ticker.change_pct > 0 else " 🔴"
    return line


def format_error_line(symbol: str) -> str:
    """异常时返回一行占位文本。"""

    return f"{symbol} 现价：N/A 振幅：N/A"


def build_message(minute_start: datetime, lines: list[str]) -> str:
    """组装最终发送到飞书的纯文本内容。"""

    minute_text = minute_start.astimezone().strftime("%Y-%m-%d %H:%M")
    return "\n".join([f"币安永续分钟行情 {minute_text}", *lines])


def get_current_minute_start(send_delay_seconds: int) -> datetime:
    """基于发送延迟推导当前整分钟开始时间。"""

    now = time.time() - send_delay_seconds
    current_minute_epoch = int(now // 60) * 60
    return datetime.fromtimestamp(current_minute_epoch, tz=timezone.utc)


def sleep_until_next_round(send_delay_seconds: int) -> None:
    """睡眠到下一个整分钟后的固定偏移点。"""

    now = time.time()
    next_run = ((int(now) // 60) + 1) * 60 + send_delay_seconds
    sleep_seconds = max(0.0, next_run - now)
    time.sleep(sleep_seconds)
