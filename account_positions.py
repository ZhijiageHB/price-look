"""查询币安 U 本位合约当前持仓，每五分钟发送到飞书。

从项目内 `.env` 读取配置，查询当前非空仓持仓，汇总后推送到飞书机器人。
"""

from __future__ import annotations

import logging
import time

from binance_client import BinanceClient
from config import load_settings
from feishu_bot import FeishuBot


def format_position_line(symbol: str, value: float, digits: int = 2) -> str:
    """统一格式化数值，避免输出过长。"""

    return f"{symbol}{value:.{digits}f}".rstrip("0").rstrip(".")


def build_position_message(positions, minute_text: str) -> str:
    """组装持仓消息：每个币对一行，总收益在最下方。"""

    lines: list[str] = [f"合约持仓汇总 {minute_text}"]
    total_profit = 0.0

    # 按收益率从高到低排序，收益率相同则按收益从高到低
    sorted_positions = sorted(
        positions,
        key=lambda p: (p.roi_pct if p.roi_pct is not None else float("-inf"), p.unrealized_profit),
        reverse=True,
    )

    for position in sorted_positions:
        roi_text = "N/A" if position.roi_pct is None else f"{position.roi_pct:+.2f}%"
        side_text = "多" if position.quantity > 0 else "空"
        lines.append(
            f"{position.symbol} {side_text} "
            f"均价：{format_position_line('', position.entry_price)} "
            f"现价：{format_position_line('', position.mark_price)} "
            f"保证金：{format_position_line('', position.initial_margin)} "
            f"收益：{position.unrealized_profit:+.2f} "
            f"收益率：{roi_text}"
        )
        total_profit += position.unrealized_profit

    lines.append(f"总收益：{total_profit:+.2f} USDT")
    return "\n".join(lines)


def main() -> None:
    """启动持仓监控循环，每五分钟查询并推送到飞书。"""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    try:
        settings = load_settings()
        client = BinanceClient(
            settings.binance_base_url,
            settings.request_timeout,
            api_key=settings.binance_api_key,
            api_secret=settings.binance_api_secret,
        )
        feishu_bot = FeishuBot(settings.feishu_webhook, settings.request_timeout)
    except Exception as exc:  # noqa: BLE001
        logging.error("初始化失败: %s", exc)
        return

    interval_seconds = 60  # 2 分钟
    logging.info("持仓监控启动，每 %d 秒推送一次", interval_seconds)

    while True:
        try:
            positions = client.fetch_open_positions()
            if not positions:
                logging.info("当前没有合约持仓，跳过本轮")
            else:
                from datetime import datetime, timezone

                minute_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
                message = build_position_message(positions, minute_text)
                feishu_bot.send_text(message)
                logging.info("飞书推送成功，共 %d 个持仓", len(positions))
        except Exception:  # noqa: BLE001
            logging.exception("本轮持仓查询或推送失败")

        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
