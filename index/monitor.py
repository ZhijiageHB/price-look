"""大盘指数监控（独立运行）。

每 2 分钟推送全球主要指数到飞书。
非交易时段不发送。
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from config import load_settings
from feishu_bot import FeishuBot
from index.data import (
    IndexQuote,
    _REGION_GROUPS,
    fetch_indices,
    filter_trading,
)

HEADER = "【全球大盘指数】"


def build_index_message(data: dict[str, IndexQuote]) -> str:
    """根据区域分组，构建带分隔线的大盘消息。"""
    lines: list[str] = []
    for region_name, keys in _REGION_GROUPS:
        region_items = [(k, data[k]) for k in keys if k in data]
        if not region_items:
            continue
        # 分隔线
        if lines:
            lines.append(SEPARATOR)
        lines.append(region_name)
        for key, item in region_items:
            lines.append(_format_line(item))
    return HEADER + "\n".join(lines)


SEPARATOR = "─" * 18


def _format_line(item: IndexQuote) -> str:
    """格式化单个指数行。"""
    if item.price is not None:
        if item.change_pct is not None:
            change_str = f"{item.change_pct:+.2f}%"
        else:
            change_str = "--"
        line = f"{item.symbol}  {item.name}: {item.price:.2f}  {change_str}"
    else:
        line = f"{item.symbol}  {item.name}: 获取失败"

    return f"{line}  [{item.status}]"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    settings = load_settings()
    feishu_bot = FeishuBot(settings.feishu_index_webhook, settings.request_timeout)

    interval = 120  # 2 分钟
    logging.info("大盘指数监控启动，每 %d 秒推送一次", interval)

    while True:
        time.sleep(interval)
        try:
            data = fetch_indices()
            trading = filter_trading(data)
            if not trading:
                logging.info("当前无交易中的指数，跳过推送")
                continue
            message = build_index_message(trading)
            feishu_bot.send_text(message)
            logging.info("飞书推送成功，共 %d 个指数", len(trading))
        except Exception:  # noqa: BLE001
            logging.exception("本轮查询或推送失败")


if __name__ == "__main__":
    main()
