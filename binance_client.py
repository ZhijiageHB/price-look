"""币安行情访问层。

负责请求币安 U 本位永续合约 1 分钟 K 线，并转换成当前项目需要的分钟涨跌数据结构。
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests


@dataclass(frozen=True)
class MinuteTicker:
    """描述一个币对在上一分钟的收盘结果。"""

    symbol: str
    open_price: float
    close_price: float
    change_pct: float
    direction: str
    minute_start: datetime


@dataclass(frozen=True)
class PositionInfo:
    """描述一个合约持仓的关键字段。"""

    symbol: str
    position_side: str
    quantity: float
    entry_price: float
    break_even_price: float
    mark_price: float
    unrealized_profit: float
    leverage: int
    notional: float
    liquidation_price: float
    margin_type: str
    estimated_margin: float
    initial_margin: float
    roi_pct: float | None


class BinanceClient:
    """封装币安 REST API 调用。"""

    def __init__(
        self,
        base_url: str,
        timeout: int,
        api_key: str = "",
        api_secret: str = "",
    ) -> None:
        """初始化请求会话，复用连接降低轮询开销。"""

        self.base_url = base_url
        self.timeout = timeout
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()

    def _sign_params(self, params: dict[str, int | str]) -> str:
        """对签名参数进行 HMAC-SHA256 签名。"""

        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{query_string}&signature={signature}"

    def _signed_get(self, path: str, params: dict[str, int | str] | None = None) -> list[dict] | dict:
        """发送币安签名 GET 请求。

        关键业务逻辑：查询用户合约持仓属于私有接口，必须带 API Key、timestamp 和 signature。
        """

        if not self.api_key or not self.api_secret:
            raise ValueError("缺少 BINANCE_API_KEY 或 BINANCE_API_SECRET，请先在 .env 中配置。")

        payload = {
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000,
        }
        if params:
            payload.update(params)

        signed_query = self._sign_params(payload)
        response = self.session.get(
            f"{self.base_url}{path}?{signed_query}",
            headers={"X-MBX-APIKEY": self.api_key},
            timeout=self.timeout,
        )

        if not response.ok:
            try:
                error_payload = response.json()
                error_message = error_payload.get("msg", response.text)
            except ValueError:
                error_message = response.text
            raise ValueError(f"币安私有接口返回异常: {error_message}")

        return response.json()

    def fetch_previous_minute_ticker(
        self,
        symbol: str,
        current_minute_start: datetime,
    ) -> MinuteTicker:
        """查询上一分钟 U 本位永续合约 K 线，并计算分钟涨跌和方向。

        这里直接用上一分钟的 open/close 做涨跌，避免本地自行采样带来的偏差。
        """

        previous_minute_start = current_minute_start - timedelta(minutes=1)
        params = {
            "symbol": symbol,
            "interval": "1m",
            "startTime": int(previous_minute_start.timestamp() * 1000),
            "endTime": int(current_minute_start.timestamp() * 1000) - 1,
            "limit": 1,
        }
        response = self.session.get(
            f"{self.base_url}/fapi/v1/klines",
            params=params,
            timeout=self.timeout,
        )

        if not response.ok:
            try:
                error_payload = response.json()
                error_message = error_payload.get("msg", response.text)
            except ValueError:
                error_message = response.text
            raise ValueError(f"{symbol} 接口返回异常: {error_message}")

        payload = response.json()

        if not payload:
            raise ValueError(f"{symbol} 在该分钟没有返回 K 线数据。")

        kline = payload[0]
        open_price = float(kline[1])
        close_price = float(kline[4])
        change_pct = 0.0 if open_price == 0 else ((close_price - open_price) / open_price) * 100

        if change_pct > 0:
            direction = "上涨"
        elif change_pct < 0:
            direction = "下跌"
        else:
            direction = "持平"

        return MinuteTicker(
            symbol=symbol,
            open_price=open_price,
            close_price=close_price,
            change_pct=change_pct,
            direction=direction,
            minute_start=previous_minute_start.astimezone(timezone.utc),
        )

    def fetch_open_positions(self) -> list[PositionInfo]:
        """查询当前所有非空仓合约持仓。

        收益率这里按“未实现收益 / 估算仓位保证金”计算。
        估算仓位保证金使用 `abs(notional) / leverage`，便于快速查看当前仓位表现。
        """

        payload = self._signed_get("/fapi/v3/positionRisk")
        if not isinstance(payload, list):
            raise ValueError("持仓接口返回格式异常。")

        positions: list[PositionInfo] = []
        for item in payload:
            quantity = float(item["positionAmt"])
            if quantity == 0:
                continue

            notional = float(item["notional"])
            initial_margin = float(item.get("initialMargin", "0") or 0)
            # 从初始保证金和名义价值反推杠杆倍数，币安 positionRisk 接口不直接返回 leverage
            leverage = round(abs(notional) / initial_margin) if initial_margin > 0 else 1
            estimated_margin = initial_margin
            unrealized_profit = float(item["unRealizedProfit"])
            roi_pct = None
            if estimated_margin > 0:
                roi_pct = (unrealized_profit / estimated_margin) * 100

            positions.append(
                PositionInfo(
                    symbol=item["symbol"],
                    position_side=item["positionSide"],
                    quantity=quantity,
                    entry_price=float(item["entryPrice"]),
                    break_even_price=float(item.get("breakEvenPrice", "0") or 0),
                    mark_price=float(item["markPrice"]),
                    unrealized_profit=unrealized_profit,
                    leverage=leverage,
                    notional=notional,
                    liquidation_price=float(item.get("liquidationPrice", "0") or 0),
                    margin_type=item.get("marginType", "cross"),
                    estimated_margin=estimated_margin,
                    initial_margin=initial_margin,
                    roi_pct=roi_pct,
                )
            )

        positions.sort(key=lambda item: abs(item.unrealized_profit), reverse=True)
        return positions
