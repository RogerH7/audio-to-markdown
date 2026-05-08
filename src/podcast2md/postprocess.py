from __future__ import annotations

import os
from typing import Any


SYSTEM_PROMPT = """你是一个中文知识库整理助手。你的任务是把播客/视频转录稿整理成可靠的 Markdown 笔记。
要求：
1. 不编造转录稿中没有的信息。
2. 保留重要观点、术语、人名、书名和时间线。
3. 输出结构要适合 Obsidian/Markdown 知识库。
4. 如果转录稿质量明显有误，要在“待校对”中列出疑点。
"""


USER_TEMPLATE = """请整理下面这份转录稿。

来源标题：{title}
来源链接：{url}
平台：{platform}

请输出以下小节：
## 摘要
## 关键观点
## 章节大纲
## 可沉淀知识点
## 待校对

转录稿：
{transcript}
"""


class PostProcessor:
    def process(self, *, title: str, url: str, platform: str, transcript: str) -> str:
        raise NotImplementedError


class DeepSeekPostProcessor(PostProcessor):
    def __init__(self, options: dict[str, Any]) -> None:
        self.api_key_env = options.get("api_key_env", "DEEPSEEK_API_KEY")
        self.base_url = options.get("base_url", "https://api.deepseek.com")
        self.model = options.get("model", "deepseek-v4-flash")
        self.max_input_chars = int(options.get("max_input_chars", 90000))

    def process(self, *, title: str, url: str, platform: str, transcript: str) -> str:
        from openai import OpenAI

        api_key = os.getenv(self.api_key_env, "")
        if not api_key:
            raise RuntimeError(f"Missing API key environment variable: {self.api_key_env}")

        clipped = transcript[: self.max_input_chars]
        client = OpenAI(api_key=api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_TEMPLATE.format(
                        title=title,
                        url=url,
                        platform=platform,
                        transcript=clipped,
                    ),
                },
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""


class NoopPostProcessor(PostProcessor):
    def process(self, *, title: str, url: str, platform: str, transcript: str) -> str:
        return "## 摘要\n\n（未启用文本后处理。）\n"


def build_postprocessor(config: dict[str, Any]) -> PostProcessor:
    post = config.get("postprocess", {})
    provider = post.get("provider", "deepseek")
    if provider == "deepseek":
        return DeepSeekPostProcessor(post.get("deepseek", {}))
    if provider in {"none", "noop"}:
        return NoopPostProcessor()
    raise ValueError(f"Unsupported postprocess provider: {provider}")
