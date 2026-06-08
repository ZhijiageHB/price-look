# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

币安永续合约分钟行情监控机器人。每分钟轮询币安 USDⓈ-M Futures 1m Kline 接口，将各币对的涨跌汇总后推送到飞书群机器人。附带一个独立的合约持仓查询工具。

## 常用命令

```bash
# 安装依赖
python3 -m pip install -r requirements.txt

# 启动主程序（分钟行情监控循环）
python3 main.py

# 查询当前合约持仓
python3 account_positions.py
```

无测试、无构建步骤、无 linter 配置。

## 架构

扁平单目录结构，5 个 Python 源文件，无子包：

- **main.py** — 入口。无限循环：sleep 到下一整分钟 + 延迟偏移 → 逐个币对拉取上一分钟 K 线 → 格式化 → 发送飞书。无效 symbol 会被缓存跳过。
- **config.py** — 配置层。自实现的 `.env` 解析器（非 python-dotenv），回退到系统环境变量，返回冻结的 `Settings` dataclass。
- **binance_client.py** — 币安 API 客户端。公开接口 `fetch_previous_minute_ticker()` 拉取 1m K 线计算 open/close/change；私有接口 `fetch_open_positions()` 用 HMAC-SHA256 签名查询持仓。
- **feishu_bot.py** — 飞书 webhook 发送器，纯文本消息。
- **account_positions.py** — 独立脚本，查询并打印当前合约持仓及 ROI。

## 核心数据结构

均为 frozen dataclass：

- `Settings` — 运行配置（API key/secret、webhook、symbol 列表、超时、延迟）
- `MinuteTicker` — 单币对 1m K 线结果（symbol、open、close、change_pct、direction、minute_start）
- `PositionInfo` — 持仓详情（symbol、数量、开仓价、标记价、未实现盈亏、ROI）

## 配置

所有运行时配置通过项目根目录 `.env` 文件管理，配置项见 README。关键项：

- `SYMBOLS` — 逗号分隔的币对列表
- `SEND_DELAY_SECONDS` — 整分钟后延迟秒数（默认 2）
- 涨跌幅超过 ±0.2% 时追加 🟢/🔴 预警符号（硬编码在 `main.py:format_line()`）

## 注意事项

- `.env` 含真实 API 凭证，`.gitignore` 未排除 `.env`，初始化 git 仓库前需先处理。
- 代码语言为中文（注释、docstring、用户消息均为中文）。
