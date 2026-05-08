from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests

import _bootstrap  # noqa: F401
from podcast2md import db
from podcast2md.config import ensure_paths, load_config
from podcast2md.markdown import render_markdown, write_markdown
from podcast2md.postprocess import build_postprocessor
from podcast2md.transcript import extract_segments, plain_transcript
from podcast2md.url_utils import source_platform


def _guess_title(task_id: int) -> str:
    audio_dir = Path("data/audio")
    if not audio_dir.exists():
        return f"task-{task_id}"
    candidates = sorted(audio_dir.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return f"task-{task_id}"
    name = candidates[0].stem
    if name.endswith(".mono"):
        name = name[:-5]
    return name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Complete a queue task from an already-finished Aliyun DashScope ASR task."
    )
    parser.add_argument("queue_task_id", type=int)
    parser.add_argument("asr_task_id")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    ensure_paths(config)
    queue_db = config["paths"]["queue_db"]
    asr_opts = config.get("asr", {}).get("aliyun_paraformer_v2", {})
    api_key = os.getenv(asr_opts.get("api_key_env", "DASHSCOPE_API_KEY"), "")
    if not api_key:
        raise SystemExit("Missing DASHSCOPE_API_KEY")

    from dashscope.audio.asr import Transcription

    response = Transcription.fetch(args.asr_task_id, api_key=api_key)
    if response.status_code != 200:
        raise SystemExit(f"Failed to fetch ASR task: {response}")
    status = response.output.get("task_status") or response.output.get("status")
    if status != "SUCCEEDED":
        raise SystemExit(f"ASR task is not completed: {status}")

    result_url = response.output["results"][0]["transcription_url"]
    result_resp = requests.get(result_url, timeout=120)
    result_resp.raise_for_status()
    asr_result = result_resp.json()
    asr_result["_task_id"] = args.asr_task_id

    asr_json_dir = Path(config["paths"]["asr_json_dir"])
    asr_json_dir.mkdir(parents=True, exist_ok=True)
    asr_json_path = asr_json_dir / f"task-{args.queue_task_id}.json"
    asr_json_path.write_text(json.dumps(asr_result, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = db.list_tasks(queue_db, limit=200)
    row = next((item for item in rows if int(item["id"]) == args.queue_task_id), None)
    if row is None:
        raise SystemExit(f"Queue task #{args.queue_task_id} not found")

    title = args.title or _guess_title(args.queue_task_id)
    segments = extract_segments(asr_result)
    transcript = plain_transcript(segments)
    platform = row["platform"] or source_platform(row["url"])
    summary = build_postprocessor(config).process(
        title=title,
        url=row["url"],
        platform=platform,
        transcript=transcript,
    )
    content = render_markdown(
        title=title,
        url=row["url"],
        platform=platform,
        metadata={"asr_json_path": str(asr_json_path), "asr_task_id": args.asr_task_id},
        summary_markdown=summary,
        segments=segments,
        include_full_transcript=bool(config.get("markdown", {}).get("include_full_transcript", True)),
        timezone=config.get("markdown", {}).get("timezone", "Asia/Shanghai"),
    )
    output_path = write_markdown(config["paths"]["output_dir"], title, content)
    db.mark_task_success(
        queue_db,
        args.queue_task_id,
        str(output_path),
        {"asr_json_path": str(asr_json_path), "asr_task_id": args.asr_task_id},
    )
    print(f"Completed task #{args.queue_task_id}: {output_path}")


if __name__ == "__main__":
    main()
