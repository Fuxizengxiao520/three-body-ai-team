"""OpenAI 兼容模型客户端，只依赖 Python 标准库。"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"


class LLMError(RuntimeError):
    pass


@dataclass
class Reply:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    simulated: bool = False


class LLM:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 60,
        retries: int = 2,
        mock: bool = False,
    ):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = (
            base_url or os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.model = model or os.environ.get("LLM_MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        self.retries = retries
        self.mock = mock

    def chat(self, system: str, user: str, temperature: float = 0.3) -> Reply:
        if self.mock:
            return self._mock(system, user)
        if not self.api_key:
            raise LLMError("缺少 DEEPSEEK_API_KEY，或改用 --mock 离线演示")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }
        url = self.base_url + "/chat/completions"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        body = None
        last_error = None
        for attempt in range(self.retries + 1):
            request = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.api_key,
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
                last_error = None
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error
                if attempt < self.retries:
                    time.sleep(1.5 * (attempt + 1))
        if last_error is not None or body is None:
            raise LLMError("模型请求失败: " + str(last_error))
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMError("响应格式异常: " + str(error)) from error
        usage = body.get("usage", {}) or {}
        return Reply(
            text=text,
            model=body.get("model", self.model),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            cached_input_tokens=int(
                usage.get("prompt_cache_hit_tokens")
                or usage.get("cached_tokens")
                or 0
            ),
        )

    def _mock(self, system: str, user: str) -> Reply:
        match = re.search(r"你是三体 AI 团队的(.+?)，岗位是", system)
        name = match.group(1) if match else ""
        if "临时会议" in user:
            if name == "维德":
                text = "我负责拆单与验收，罗辑先出简报，云天明再成稿，最后交人工放行。"
            elif name == "罗辑":
                text = "我交 3 条带来源和日期的前沿资讯，需要主题边界明确。"
            else:
                text = "我基于罗辑的简报成稿，只引用上游出现过的数字。"
        elif name == "罗辑":
            text = (
                "# 前沿资讯简报\n\n"
                "1. 来源 x.ai/news/introducing-grok-bot，日期 2026-08-11，"
                "多个 Bot 可并行并在群聊中互相派活。可信度 高，官方一手。\n"
                "2. 来源 anthropic.com/engineering/building-c-compiler，日期 2026，"
                "16 个并行 agent 完成编译器，成本约 20000 美元。可信度 高，工程博客。\n"
                "3. 来源 api-docs.deepseek.com/quick_start/pricing，日期 2026-11-13，"
                "flash 输出谷时每 1M tokens 0.6 美元。可信度 高，官方定价页。\n\n"
                "备注 以上为离线演示数据，真实运行会替换为模型输出。"
            )
        elif name == "云天明":
            text = (
                "# 文案初稿\n\n"
                "一个团队能开会，能交接，能互相挑错，才算真的在协作。\n"
                "三体 AI 团队把任务拆成任务卡，罗辑找料，云天明成稿，维德逐条验收，"
                "最后一道门留给人。每一步都留痕，账单也留痕。\n\n"
                "行动指引 先跑一次离线演示，再决定要不要接真实模型。\n\n"
                "备注 以上为离线演示数据。"
            )
        elif name == "维德":
            text = (
                "# 验收意见\n\n"
                "维德只做验收，不产出内容。逐条核对任务卡的验收标准，"
                "不确定项标记为待人工确认。"
            )
        else:
            text = "收到，按分工执行。"
        return Reply(
            text=text,
            model="mock-local",
            input_tokens=max(1, len(user) // 2),
            output_tokens=max(1, len(text) // 2),
            simulated=True,
        )
