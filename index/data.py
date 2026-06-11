"""获取全球主要大盘指数数据。

数据来源：东方财富 push2 行情接口（非官方，前端同款）。
国内直连，无需代理。
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# 时区常量
# ---------------------------------------------------------------------------
_ET = timezone(timedelta(hours=-5))
_KST = timezone(timedelta(hours=9))
_JST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# 数据定义
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IndexQuote:
    """单只指数的行情摘要。"""
    symbol: str          # key，如 "nasdaq"
    name: str            # 全名，如 "纳斯达克综合指数"
    price: Optional[float]   # 最新价
    change_pct: Optional[float]  # 涨跌幅 %
    is_trading: bool     # 当前是否处于交易时段
    status: str          # "交易中" / "已收盘" / "休市"

# 交易时段配置：(开市时, 开市分, 收盘时, 收盘分, 时区)
_TRADING_HOURS: dict[str, tuple[int, int, int, int, timezone]] = {
    "nasdaq": (9, 30, 16, 0, _ET),
    "sp500":  (9, 30, 16, 0, _ET),
    "djia":   (9, 30, 16, 0, _ET),
    "kospi":  (9, 0, 15, 30, _KST),
    "n225":   (9, 0, 15, 0, _JST),
}

# 东方财富 secid 映射
_SECIDS = {
    "nasdaq": "100.NDX",
    "sp500":  "100.SPX",
    "djia":   "100.DJIA",
    "kospi":  "100.KS11",
    "n225":   "100.N225",
}

# 输出顺序
_ORDER = ["nasdaq", "sp500", "djia", "kospi", "n225"]

# 区域分组：(标题, [key, ...])
_REGION_GROUPS = [
    ("🇺🇸 美国", ["nasdaq", "sp500", "djia"]),
    ("🇰🇷 韩国", ["kospi"]),
    ("🇯🇵 日本", ["n225"]),
]

_NAMES = {
    "nasdaq": "纳斯达克综合指数",
    "sp500":  "标普500指数",
    "djia":   "道琼斯工业指数",
    "kospi":  "韩国综合指数",
    "n225":   "日经225指数",
}

# 东方财富接口字段
_FIELDS = "f43,f57,f58,f169,f170,f171"

# ---------------------------------------------------------------------------
# 交易时段判断
# ---------------------------------------------------------------------------

def _is_trading_now(key: str, now_utc: Optional[datetime] = None) -> bool:
    if key not in _TRADING_HOURS:
        return False
    open_h, open_m, close_h, close_m, tz = _TRADING_HOURS[key]
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    local = now_utc.astimezone(tz)
    if local.weekday() >= 5:
        return False
    current = local.hour * 60 + local.minute
    return open_h * 60 + open_m <= current < close_h * 60 + close_m


def _is_closed_today(key: str, now_utc: datetime) -> bool:
    if key not in _TRADING_HOURS:
        return False
    _, _, close_h, close_m, tz = _TRADING_HOURS[key]
    local = now_utc.astimezone(tz)
    if local.weekday() >= 5:
        return False
    current = local.hour * 60 + local.minute
    return current >= close_h * 60 + close_m


def _status(key: str, now_utc: datetime) -> str:
    if _is_trading_now(key, now_utc):
        return "交易中"
    if _is_closed_today(key, now_utc):
        return "已收盘"
    return "休市"

# ---------------------------------------------------------------------------
# 东方财富接口
# ---------------------------------------------------------------------------

def _fetch_eastmoney(secid: str, max_retries: int = 3) -> Optional[dict]:
    """调用东方财富 push2 实时行情接口，返回 JSON data 字段。

    国内直连，显式绕过系统代理。需要 Referer 头才能正常返回数据。
    带重试机制，应对限流。
    """
    import time as _time
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": secid,
        "fields": _FIELDS,
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
    }
    headers = {
        "Referer": "https://quote.eastmoney.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    for attempt in range(max_retries):
        try:
            # 每次创建新的 session，避免连接复用问题
            session = requests.Session()
            session.trust_env = False  # 忽略环境变量中的代理设置
            resp = session.get(url, params=params, headers=headers, timeout=5)
            resp.raise_for_status()
            body = resp.json()
            session.close()
            if body.get("data"):
                return body["data"]
            return None
        except Exception:
            if attempt < max_retries - 1:
                _time.sleep(1)
    return None


def fetch_indices() -> dict[str, IndexQuote]:
    """批量拉取所有指数行情。

    返回 ``{key: IndexQuote}`` 字典。单只失败不影响其他。

    东方财富接口所有数值均乘以 100，需要除以 100 还原。
    为避免限流，每次请求间隔 2 秒。
    """
    import time as _time
    now = datetime.now(timezone.utc)
    result: dict[str, IndexQuote] = {}

    for i, key in enumerate(_ORDER):
        if i > 0:
            _time.sleep(2)
        secid = _SECIDS[key]
        data = _fetch_eastmoney(secid)

        if data and data.get("f43") is not None:
            # f43=最新价, f169=涨跌额, f170=涨跌幅（均需除以100）
            price = data["f43"] / 100
            change_pct = data["f170"] / 100
            result[key] = IndexQuote(
                symbol=key,
                name=_NAMES[key],
                price=round(price, 2),
                change_pct=round(change_pct, 2),
                is_trading=_is_trading_now(key, now),
                status=_status(key, now),
            )
        else:
            result[key] = IndexQuote(
                symbol=key,
                name=_NAMES[key],
                price=None,
                change_pct=None,
                is_trading=_is_trading_now(key, now),
                status=_status(key, now),
            )

    return result


def filter_trading(data: dict[str, IndexQuote]) -> dict[str, IndexQuote]:
    """只返回交易中的指数。"""
    return {k: v for k, v in data.items() if v.status == "交易中"}
