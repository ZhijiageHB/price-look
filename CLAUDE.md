# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

币安永续合约分钟行情监控机器人。每分钟轮询币安 USDⓈ-M Futures 1m Kline 接口，将各币对的涨跌汇总后推送到飞书群机器人。附带合约持仓监控和全球大盘指数监控功能。

## 常用命令

```bash
# 安装依赖
python3 -m pip install -r requirements.txt

# 三合一启动
python3 main.py

# 单独运行
python3 price/monitor.py     # 分钟行情
python3 position/monitor.py  # 持仓
python3 index/monitor.py     # 大盘指数
```

无测试、无构建步骤、无 linter 配置。

## 架构

共享模块在根目录，三个功能分文件夹：

- **config.py** — 配置层。自实现 `.env` 解析器，回退到系统环境变量，返回冻结的 `Settings` dataclass。
- **binance_client.py** — 币安 API 客户端。公开接口拉取 1m K 线；私有接口用 HMAC-SHA256 签名查询持仓。
- **feishu_bot.py** — 飞书 webhook 发送器，纯文本消息。
- **price/** — 自选币种分钟行情。`formatter.py` 提供格式化工具，`monitor.py` 为独立入口。
- **position/** — 合约持仓监控。`monitor.py` 含 `build_position_message` 供 main.py 线程调用。
- **index/** — 全球大盘指数。`data.py` 通过 yfinance 获取数据并判断交易时段，`monitor.py` 为独立入口。

## 核心数据结构

均为 frozen dataclass：

- `Settings` — 运行配置（三个飞书 webhook、API key/secret、symbol 列表、超时、延迟）
- `MinuteTicker` — 单币对 1m K 线结果
- `PositionInfo` — 持仓详情

## 注意事项

- 三个功能使用三个独立的飞书 webhook，分别在 `.env` 中配置。
- 大盘指数通过 yfinance 获取，需设置代理（默认 `127.0.0.1:7897`）。
- `.env` 含真实 API 凭证，已在 `.gitignore` 中排除。
