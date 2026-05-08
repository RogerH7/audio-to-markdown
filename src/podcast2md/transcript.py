from __future__ import annotations

from typing import Any


def _seconds(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number > 1000:
        return number / 1000.0
    return number


def format_timestamp(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def extract_segments(asr_result: dict[str, Any]) -> list[dict[str, Any]]:
    raw = asr_result.get("sentences") or asr_result.get("segments") or asr_result.get("utterances") or []
    if not raw and asr_result.get("transcripts"):
        transcripts = asr_result.get("transcripts") or []
        for transcript in transcripts:
            if isinstance(transcript, dict) and transcript.get("sentences"):
                raw.extend(transcript["sentences"])
            else:
                raw.append(transcript)
    segments: list[dict[str, Any]] = []
    for item in raw:
        text = (item.get("text") or item.get("sentence") or "").strip()
        if not text:
            continue
        start = _seconds(item.get("begin_time", item.get("start", item.get("start_time"))))
        end = _seconds(item.get("end_time", item.get("end", item.get("end_time"))))
        speaker = item.get("speaker_id", item.get("speaker", ""))
        segments.append({"start": start, "end": end, "speaker": speaker, "text": text})
    if not segments:
        text = asr_result.get("text") or asr_result.get("transcript") or ""
        if text:
            segments.append({"start": 0.0, "end": 0.0, "speaker": "", "text": text.strip()})
    return segments


def plain_transcript(segments: list[dict[str, Any]]) -> str:
    lines = []
    for seg in segments:
        speaker = seg.get("speaker")
        prefix = f"说话人{speaker} " if speaker not in ("", None) else ""
        lines.append(f"[{format_timestamp(seg['start'])}] {prefix}{seg['text']}")
    return "\n".join(lines)
