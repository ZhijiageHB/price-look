"""大盘指数监控（独立运行）。

每 N 分钟推送全球主要指数到飞书。
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from config import load_settings
from feishu_bot import FeishuBot
from index.data import INDEX_MAP, build_index_message, fetch_index_data


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    settings = load_settings()
    feishu_bot = FeishuBot(settings.feishu_index_webhook, settings.request_timeout)

    tickers = list(INDEX_MAP.keys())
    interval = 120  # 2 分钟
    logging.info("大盘指数监控启动，每 %d 秒推送一次", interval)

    while True:
        time.sleep(interval)
        try:
            data = fetch_index_data(tickers)
            if not data:
                logging.info("本轮无有效数据，跳过")
                continue
            minute_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            message = build_index_message(data, minute_text)
            feishu_bot.send_text(message)
            logging.info("飞书推送成功，共 %d 个指数", len(data))
        except Exception:  # noqa: BLE001
            logging.exception("本轮查询或推送失败")


if __name__ == "__main__":
    main()
