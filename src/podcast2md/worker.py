from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from . import db
from .audio import normalize_audio
from .asr import build_asr
from .config import ensure_paths, load_config
from .downloader import download_source
from .markdown import render_markdown, write_markdown
from .notifier import LarkNotifier
from .postprocess import build_postprocessor
from .storage import build_storage
from .transcript import extract_segments, plain_transcript


def _row_metadata(row: Any) -> dict[str, Any]:
    try:
        return json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        return {}


def process_task(config: dict[str, Any], task: Any, *, dry_run: bool = False) -> Path:
    paths = config["paths"]
    download_cfg = config.get("download", {})
    markdown_cfg = config.get("markdown", {})
    storage_cfg = config.get("storage", {})

    if dry_run:
        title = f"DRY-RUN task {task['id']}"
        segments = [
            {"start": 0, "end": 5, "speaker": "0", "text": f"已接收链接：{task['url']}"},
            {"start": 6, "end": 10, "speaker": "0", "text": "真实运行时会下载音频、调用阿里云 Paraformer V2、再用 DeepSeek V4 Flash 整理。"},
        ]
        content = render_markdown(
            title=title,
            url=task["url"],
            platform=task["platform"],
            metadata={"duration": 10},
            summary_markdown="## 摘要\n\n这是一份 dry-run 验证文档。",
            segments=segments,
            include_full_transcript=True,
            timezone=markdown_cfg.get("timezone", "Asia/Shanghai"),
        )
        return write_markdown(paths["output_dir"], title, content)

    print("[worker] downloading source audio...")
    downloaded = download_source(
        task["url"],
        paths["audio_dir"],
        cookie_file=download_cfg.get("cookie_file") or None,
        cookies_from_browser=download_cfg.get("cookies_from_browser") or None,
    )
    print(f"[worker] downloaded audio: {downloaded.audio_path}")
    print("[worker] normalizing audio...")
    normalized = normalize_audio(downloaded.audio_path, paths["audio_dir"])
    print(f"[worker] normalized audio: {normalized}")

    print("[worker] uploading audio to object storage...")
    storage = build_storage(config)
    uploaded = storage.upload(normalized)
    print(f"[worker] uploaded audio object: {uploaded.object_key}")

    print("[worker] submitting ASR task...")
    asr_provider = build_asr(config)
    asr_result = asr_provider.transcribe(uploaded.public_url)
    print("[worker] ASR completed.")

    retention_days = int(storage_cfg.get("retention_days", 0) or 0)
    delete_after_asr = bool(storage_cfg.get("delete_after_asr", True)) and retention_days <= 0
    if delete_after_asr and uploaded.object_key:
        try:
            storage.delete(uploaded.object_key)
            print(f"[worker] deleted temporary audio object: {uploaded.object_key}")
        except Exception as exc:
            print(f"[worker] warning: failed to delete temporary audio object: {exc}")
    elif uploaded.object_key:
        print(
            "[worker] retained temporary audio object "
            f"for cleanup after {retention_days} day(s): {uploaded.object_key}"
        )

    asr_json_dir = Path(paths["asr_json_dir"])
    asr_json_dir.mkdir(parents=True, exist_ok=True)
    asr_json_path = asr_json_dir / f"task-{task['id']}.json"
    asr_json_path.write_text(json.dumps(asr_result, ensure_ascii=False, indent=2), encoding="utf-8")

    segments = extract_segments(asr_result)
    transcript = plain_transcript(segments)

    print("[worker] running text post-processing...")
    postprocessor = build_postprocessor(config)
    summary = postprocessor.process(
        title=downloaded.title,
        url=task["url"],
        platform=task["platform"],
        transcript=transcript,
    )
    print("[worker] text post-processing completed.")

    metadata = _row_metadata(task)
    metadata.update(downloaded.metadata)
    metadata.update(
        {
            "asr_json_path": str(asr_json_path),
            "storage_object_key": uploaded.object_key,
            "storage_object_deleted_after_asr": delete_after_asr,
            "storage_object_retention_days": retention_days,
        }
    )

    content = render_markdown(
        title=downloaded.title,
        url=task["url"],
        platform=task["platform"],
        metadata=metadata,
        summary_markdown=summary,
        segments=segments,
        include_full_transcript=bool(markdown_cfg.get("include_full_transcript", True)),
        timezone=markdown_cfg.get("timezone", "Asia/Shanghai"),
    )
    output_path = write_markdown(paths["output_dir"], downloaded.title, content)

    if not download_cfg.get("keep_audio", False):
        for path in {downloaded.audio_path, normalized}:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    return output_path


def run_once(config_path: str, *, dry_run: bool = False) -> bool:
    config = load_config(config_path)
    ensure_paths(config)
    queue_db = config["paths"]["queue_db"]
    task = db.peek_next_task(queue_db) if dry_run else db.claim_next_task(queue_db)
    if not task:
        print("[worker] no queued task")
        return False

    lark_cfg = config.get("lark", {})
    notifier = LarkNotifier(
        enabled=bool(lark_cfg.get("reply_enabled", True)),
        identity=lark_cfg.get("identity", "bot"),
    )

    print(f"[worker] processing task #{task['id']}: {task['url']}")
    try:
        output_path = process_task(config, task, dry_run=dry_run)
        metadata = _row_metadata(task)
        metadata["output_path"] = str(output_path)
        if dry_run:
            print(f"[worker] dry-run succeeded for task #{task['id']}: {output_path}")
            return True
        db.mark_task_success(queue_db, int(task["id"]), str(output_path), metadata)
        notifier.reply(
            task["message_id"],
            f"转写完成：#{task['id']}\n{output_path}",
            idempotency_key=f"podcast2md-success-{task['id']}",
        )
        print(f"[worker] succeeded task #{task['id']}: {output_path}")
        return True
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        db.mark_task_failed(queue_db, int(task["id"]), message)
        notifier.reply(
            task["message_id"],
            f"转写失败：#{task['id']}\n{message}",
            idempotency_key=f"podcast2md-failed-{task['id']}",
        )
        print(f"[worker] failed task #{task['id']}: {message}")
        return True


def run_loop(config_path: str, *, dry_run: bool = False, poll_interval: int = 15) -> None:
    while True:
        handled = run_once(config_path, dry_run=dry_run)
        if not handled:
            time.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run podcast/video to Markdown worker.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--poll-interval", type=int, default=15)
    args = parser.parse_args()
    if args.once:
        run_once(args.config, dry_run=args.dry_run)
    else:
        run_loop(args.config, dry_run=args.dry_run, poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
