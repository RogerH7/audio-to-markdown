from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import _bootstrap  # noqa: F401
from podcast2md.config import ensure_paths
from podcast2md.db import enqueue_url, init_db, list_tasks
from podcast2md.lark_listener import handle_event
from podcast2md.notifier import LarkNotifier
from podcast2md.worker import run_once
from podcast2md.url_utils import extract_urls


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="podcast2md-smoke-"))
    try:
        config_path = root / "config.yaml"
        config_path.write_text(
            f"""
paths:
  data_dir: {root / "data"}
  queue_db: {root / "data" / "queue.sqlite"}
  audio_dir: {root / "data" / "audio"}
  asr_json_dir: {root / "data" / "asr_json"}
  output_dir: {root / "output"}
  log_dir: {root / "logs"}
lark:
  event_key: im.message.receive_v1
  identity: bot
  reply_enabled: false
download:
  cookie_file: ""
  keep_audio: false
storage:
  provider: public_base_url
  public_base_url: https://example.com/audio
asr:
  provider: fixture
  fixture_path: {root / "fixture.json"}
postprocess:
  provider: none
markdown:
  include_full_transcript: true
  timezone: Asia/Shanghai
""".strip(),
            encoding="utf-8",
        )
        (root / "fixture.json").write_text(
            '{"transcripts":[{"begin_time":0,"end_time":1000,"speaker_id":"0","text":"测试文本"}]}',
            encoding="utf-8",
        )
        config = {
            "paths": {
                "data_dir": str(root / "data"),
                "queue_db": str(root / "data" / "queue.sqlite"),
                "audio_dir": str(root / "data" / "audio"),
                "asr_json_dir": str(root / "data" / "asr_json"),
                "output_dir": str(root / "output"),
                "log_dir": str(root / "logs"),
            }
        }
        ensure_paths(config)
        db_path = root / "data" / "queue.sqlite"
        init_db(db_path)
        task_id, created = enqueue_url(db_path, "https://www.bilibili.com/video/BV1xx411c7mD")
        assert created and task_id
        duplicated_id, duplicated_created = enqueue_url(db_path, "https://www.bilibili.com/video/BV1xx411c7mD")
        assert duplicated_id == task_id and not duplicated_created
        duplicated_id, duplicated_created = enqueue_url(db_path, "http://www.bilibili.com/video/BV1xx411c7mD")
        assert duplicated_id == task_id and not duplicated_created

        added = handle_event(
            {
                "event_id": "evt-smoke",
                "message_id": "om-smoke",
                "chat_id": "oc-smoke",
                "sender_id": "ou-smoke",
                "content": "看看这个 https://youtu.be/example",
            },
            db_path,
            LarkNotifier(enabled=False),
        )
        assert added == 1
        assert extract_urls("bilibili.com/video/BV1vy9XBrExq/?spm_id_from=333.1007") == [
            "https://www.bilibili.com/video/BV1vy9XBrExq/?spm_id_from=333.1007"
        ]

        assert run_once(str(config_path), dry_run=True)
        today_dir = root / "output" / datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
        assert today_dir.is_dir()
        assert any(today_dir.glob("*.md"))
        rows = list_tasks(db_path, limit=10)
        assert any(row["status"] == "queued" for row in rows)
        print("smoke test passed")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
