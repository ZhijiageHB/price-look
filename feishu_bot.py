"""飞书机器人发送层。

负责把格式化后的监控文本发送到飞书自定义机器人。
"""

from __future__ import annotations

import requests


class FeishuBot:
    """封装飞书机器人 webhook 调用。"""

    def __init__(self, webhook: str, timeout: int) -> None:
        """保存机器人地址，并复用 HTTP 会话。"""

        self.webhook = webhook
        self.timeout = timeout
        self.session = requests.Session()

    def send_text(self, text: str) -> None:
        """发送纯文本消息，适合当前这种简单清晰的一行一币对展示。"""

        payload = {
            "msg_type": "text",
            "content": {
                "text": text,
            },
        }
        response = self.session.post(self.webhook, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if data.get("code") not in (0, None):
            raise ValueError(f"飞书机器人返回异常: {data}")
