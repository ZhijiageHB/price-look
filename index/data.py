"""大盘指数数据层。

通过 yfinance 获取全球主要市场指数数据。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta

# 设置代理，让 yfinance 能通过 VPN 访问 Yahoo Finance
_PROXY = os.environ.get("HTTPS_PROXY", "http://127.0.0.1:7897")
os.environ.setdefault("HTTP_PROXY", _PROXY)
os.environ.setdefault("HTTPS_PROXY", _PROXY)

import yfinance as yf  # noqa: E402

# 按地区分组的大盘指数，推送时美国在最上面，其次韩国、日本
INDEX_MAP: dict[str, str] = {
    # 美国
    "^IXIC": "纳斯达克",
    "^GSPC": "标普500",
    "^DJI": "道琼斯",
    # 韩国
    "^KS11": "韩国KOSPI",
    # 日本
    "^N225": "日经225",
}

# 交易时段（当地时间）：(开盘时, 开盘分, 收盘时, 收盘分)
_TRADING_HOURS: dict[str, tuple[int, int, int, int]] = {
    "^IXIC": (9, 30, 16, 0),    # 美股 09:30-16:00 ET
    "^GSPC": (9, 30, 16, 0),
    "^DJI": (9, 30, 16, 0),
    "^KS11": (9, 0, 15, 30),    # 韩股 09:00-15:30 KST
    "^N225": (9, 0, 15, 0),     # 日股 09:00-15:00 JST
}

# 各市场时区偏移（相对于 UTC）
_TIMEZONE_OFFSET: dict[str, int] = {
    "^IXIC": -4, "^GSPC": -4, "^DJI": -4,  # EDT (UTC-4)
    "^KS11": 9,   # KST (UTC+9)
    "^N225": 9,   # JST (UTC+9)
}


def _is_trading_now(ticker: str) -> str:
    """判断当前是否在交易时段，返回状态文本。"""

    hours = _TRADING_HOURS.get(ticker)
    offset = _TIMEZONE_OFFSET.get(ticker)
    if hours is None or offset is None:
        return ""

    now_utc = datetime.now(timezone.utc)
    local_time = now_utc + timedelta(hours=offset)
    weekday = local_time.weekday()  # 0=周一, 6=周日

    if weekday >= 5:
        return "休市（周末）"

    open_h, open_m, close_h, close_m = hours
    open_time = local_time.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
    close_time = local_time.replace(hour=close_h, minute=close_m, second=0, microsecond=0)

    if open_time <= local_time <= close_time:
        return "交易中"
    elif local_time < open_time:
        return "未开盘"
    else:
        return "已收盘"


def fetch_index_data(tickers: list[str]) -> list[dict]:
    """批量获取指数实时行情。"""

    results: list[dict] = []
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.info
            price = info.get("regularMarketPrice")
            change_pct = info.get("regularMarketChangePercent")
            prev_close = info.get("regularMarketPreviousClose")

            if price is None:
                continue

            name = INDEX_MAP.get(ticker, ticker)
            status = _is_trading_now(ticker)
            results.append({
                "name": name,
                "ticker": ticker,
                "price": price,
                "change_pct": change_pct if change_pct is not None else 0.0,
                "prev_close": prev_close,
                "status": status,
            })
        except Exception:  # noqa: BLE001
            logging.warning("获取 %s 数据失败", ticker)

    return results


def filter_trading(data: list[dict]) -> list[dict]:
    """只保留当前正在交易的指数，过滤掉未开盘、已收盘、休市的。"""

    return [item for item in data if item["status"] == "交易中"]


# 地区分组：用于插入分隔线
_REGION_GROUPS: list[set[str]] = [
    {"^IXIC", "^GSPC", "^DJI"},           # 美国
    {"^KS11"},                              # 韩国
    {"^N225"},                              # 日本
]

_SEPARATOR = "─" * 20


def build_index_message(data: list[dict], minute_text: str) -> str:
    """组装指数消息：美国在最上面，其次韩国、日本、中国，不同地区用分隔线隔开。"""

    if not data:
        return ""

    # 按 INDEX_MAP 的顺序排序（美国 -> 韩国 -> 日本 -> 中国）
    order = {ticker: i for i, ticker in enumerate(INDEX_MAP)}
    data.sort(key=lambda x: order.get(x["ticker"], 999))

    # 构建 ticker -> region index 映射
    ticker_region: dict[str, int] = {}
    for i, group in enumerate(_REGION_GROUPS):
        for ticker in group:
            ticker_region[ticker] = i

    lines: list[str] = [f"大盘指数 {minute_text}"]
    last_region = -1

    for item in data:
        region = ticker_region.get(item["ticker"], 999)

        # 不同地区之间插入分隔线
        if last_region != -1 and region != last_region:
            lines.append(_SEPARATOR)
        last_region = region

        # 涨跌箭头
        arrow = "🟢" if item["change_pct"] > 0 else "🔴" if item["change_pct"] < 0 else "⚪"

        # 交易状态：交易中用绿色，休市/已收盘用灰色
        status = item.get("status", "")
        if status == "交易中":
            status_text = f"  🟢{status}"
        elif status:
            status_text = f"  ⚪{status}"
        else:
            status_text = ""

        lines.append(
            f"{item['name']}  现价：{item['price']:.2f}  "
            f"涨跌：{item['change_pct']:+.2f}%  {arrow}{status_text}"
        )

    return "\n".join(lines)
