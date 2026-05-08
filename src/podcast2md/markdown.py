from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .transcript import format_timestamp
from .url_utils import safe_filename


def render_markdown(
    *,
    title: str,
    url: str,
    platform: str,
    metadata: dict[str, Any],
    summary_markdown: str,
    segments: list[dict[str, Any]],
    include_full_transcript: bool = True,
    timezone: str = "Asia/Shanghai",
) -> str:
    now = datetime.now(ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "---",
        f'title: "{title.replace(chr(34), chr(39))}"',
        f"source: {url}",
        f"platform: {platform}",
        f"created: {now}",
        f"duration_seconds: {metadata.get('duration', '')}",
        "---",
        "",
        f"# {title}",
        "",
        f"> 来源：[{platform}]({url})",
        f"> 生成时间：{now}",
        "",
        summary_markdown.strip(),
        "",
        "## 时间戳目录",
        "",
    ]

    step = max(1, len(segments) // 20) if segments else 1
    for idx, seg in enumerate(segments):
        if idx % step == 0:
            lines.append(f"- `{format_timestamp(seg['start'])}` {seg['text'][:80]}")

    if include_full_transcript:
        lines.extend(["", "## 详细文字稿", ""])
        current_speaker = None
        for seg in segments:
            speaker = seg.get("speaker")
            speaker_label = f"说话人{speaker}" if speaker not in ("", None) else ""
            if speaker_label and speaker_label != current_speaker:
                if current_speaker is not None:
                    lines.append("")
                current_speaker = speaker_label
            prefix = f"**[{speaker_label}]** " if speaker_label else ""
            lines.append(f"{prefix}`[{format_timestamp(seg['start'])}]` {seg['text']}")

    lines.extend(["", "---", "", "*本文稿由自动化工作流生成，仅供学习和检索，建议结合原音频校对。*"])
    return "\n".join(lines).strip() + "\n"


def write_markdown(output_dir: str | Path, title: str, content: str) -> Path:
    output_dir = Path(output_dir)
    now = datetime.now().strftime("%Y/%m")
    target_dir = output_dir / now
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{safe_filename(title)}.md"
    path.write_text(content, encoding="utf-8")
    return path
