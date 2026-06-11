# 🔮 Price Look — 打工人的加密货币盯盘神器

> **上班偷偷看盘被老板发现？手机消息太多刷不到关键行情？**
> 让飞书机器人自动帮你盯盘，涨跌一目了然，再也不用反复切屏。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 😩 痛点

作为一个加密货币打工人，你一定经历过：

- 🖥️ 写代码写到一半，忍不住切到交易所看一眼行情，然后就忘了回来
- 📱 手机通知太多，真正重要的涨跌提醒淹没在消息海里
- 😰 开会时错过关键行情波动，事后才发现该操作了
- 🔍 想同时盯多个币种和大盘指数，逐个切换太麻烦

**Price Look 就是为了解决这些问题而生的。**

## ✨ 三大核心功能

把行情推送到你最常用的办公工具 — **飞书**，上班看盘就像看同事消息一样自然。

### 📊 自选币种分钟行情

每分钟自动推送所有关注币种的实时行情：

```
币安永续分钟行情 2026-06-08 16:49
MRVLUSDT 现价：282.12 开盘：281.56 收盘：282.12 振幅：+0.20%
ARMUSDT 现价：340.89 开盘：341.69 收盘：340.89 振幅：-0.23% 🔴
FLNCUSDT 现价：23.33 开盘：23.22 收盘：23.33 振幅：+0.47% 🟢
```

- 振幅超过 ±0.2% 自动标记 🟢🔴 预警，一眼看出哪个币在异动

### 💰 合约持仓监控

每两分钟推送当前合约持仓汇总，按收益率排序：

```
合约持仓汇总 2026-06-08 16:51
FLNCUSDT 多 均价：20.93 现价：23.33 保证金：16.46 收益：+33.94 收益率：+205.61%
NOKUSDT 多 均价：13.58 现价：14.65 保证金：21.06 收益：+30.84 收益率：+146.42%
总收益：+93.47 USDT
```

- 按收益率从高到低排序，最赚钱的币排在前面
- 底部显示总收益，仓位盈亏一目了然

### 🌍 全球大盘指数

每五分钟推送全球主要指数，按地区排列（美国 → 韩国 → 日本 → 中国），并显示交易时段状态：

```
大盘指数 2026-06-09 09:54
纳斯达克  现价：25929.66  涨跌：+0.86%  🟢  已收盘
标普500  现价：7405.73  涨跌：+0.30%  🟢  已收盘
道琼斯  现价：50786.01  涨跌：-0.16%  🔴  已收盘
韩国KOSPI  现价：7740.23  涋跌：+3.42%  🟢  交易中
日经225  现价：64609.78  涨跌：+0.91%  🟢  未开盘
上证指数  现价：3961.74  涨跌：+0.06%  🟢  未开盘
```

- 覆盖纳斯达克、标普500、道琼斯、KOSPI、日经225、上证、深证、创业板、恒生
- 自动判断交易中 / 未开盘 / 已收盘 / 休市（周末）

## 🚀 5 分钟上手

### 1. 安装依赖

```bash
git clone https://github.com/ZhijiageHB/price-look.git
cd price-look
python3 -m pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入你的配置：

- **飞书 Webhook**：在飞书群里添加自定义机器人，复制 webhook 地址
- **币安 API Key/Secret**：在 [币安 API 管理页面](https://www.binance.com/zh-CN/my/settings/api-management) 创建只读 Key

### 3. 启动

```bash
python3 main.py              # 全部一起跑
python3 price/monitor.py     # 只跑分钟行情
python3 position/monitor.py  # 只跑持仓
python3 index/monitor.py     # 只跑大盘指数
```

## 🏗️ 架构

```
price-look/
├── main.py                  # 三合一入口（分钟行情 + 持仓 + 大盘）
├── config.py                # 配置层：.env 解析 + 环境变量回退
├── feishu_bot.py            # 飞书 Webhook 消息发送
├── binance_client.py        # 币安 API：公开行情 + 签名私有接口
├── requirements.txt         # 依赖
├── .env.example             # 配置模板
├── price/                   # 自选币种分钟行情
│   ├── formatter.py         # 行情格式化工具
│   └── monitor.py           # 独立运行入口
├── position/                # 合约持仓监控
│   └── monitor.py
└── index/                   # 全球大盘指数
    ├── data.py              # 数据层（东方财富 push2 接口 + 交易时段判断）
    └── monitor.py           # 独立运行入口
```

## ⚙️ 配置项

| 配置项 | 必填 | 说明 | 默认值 |
|--------|------|------|--------|
| `FEISHU_WEBHOOK` | ✅ | 飞书机器人 webhook（行情+持仓） | — |
| `FEISHU_INDEX_WEBHOOK` | ❌ | 飞书机器人 webhook（大盘指数，不填则共用上面的） | 同 FEISHU_WEBHOOK |
| `BINANCE_API_KEY` | ✅ | 币安只读 API Key | — |
| `BINANCE_API_SECRET` | ✅ | 币安 API Secret | — |
| `SYMBOLS` | ❌ | 关注的币对，逗号分隔 | `BTCUSDT,ETHUSDT,...` |
| `BINANCE_BASE_URL` | ❌ | 币安接口地址 | `https://fapi.binance.com` |
| `REQUEST_TIMEOUT` | ❌ | 请求超时（秒） | `10` |
| `SEND_DELAY_SECONDS` | ❌ | 整分钟后延迟发送（秒） | `2` |

## 🛡️ 安全

- API Key 只需**只读权限**，无法进行任何交易操作
- `.env` 文件已加入 `.gitignore`，不会被提交到仓库
- 所有 API 请求通过 HTTPS 加密传输

## 📄 License

[MIT](LICENSE)
