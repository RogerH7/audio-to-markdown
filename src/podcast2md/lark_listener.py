from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from .config import load_config
from .db import enqueue_url
from .notifier import LarkNotifier
from .url_utils import extract_urls


def _stderr_logger(stream, ready_event: threading.Event) -> None:
    for line in stream:
        line = line.rstrip()
        if "[event] ready" in line:
            ready_event.set()
        print(f"[lark-cli] {line}", file=sys.stderr)


def handle_event(event: dict[str, Any], db_path: str | Path, notifier: LarkNotifier) -> int:
    content = event.get("content", "")
    urls = extract_urls(content)
    if not urls:
        return 0

    count = 0
    replies = []
    for url in urls:
        task_id, created = enqueue_url(
            db_path,
            url,
            event_id=event.get("event_id"),
            message_id=event.get("message_id") or event.get("id"),
            chat_id=event.get("chat_id"),
            sender_id=event.get("sender_id"),
            metadata={"raw_lark_event": event},
        )
        if created:
            count += 1
            replies.append(f"已加入转写队列：#{task_id}\n{url}")
        else:
            replies.append(f"这个链接已经在队列中：#{task_id}\n{url}")

    notifier.reply(
        event.get("message_id") or event.get("id"),
        "\n\n".join(replies),
        idempotency_key=f"podcast2md-enqueue-{event.get('event_id', '')}",
    )
    return count


def listen(config_path: str, *, max_events: int = 0, timeout: str | None = None) -> None:
    config = load_config(config_path)
    db_path = config["paths"]["queue_db"]
    lark = config.get("lark", {})
    notifier = LarkNotifier(
        enabled=bool(lark.get("reply_enabled", True)),
        identity=lark.get("identity", "bot"),
    )

    cmd = [
        "lark-cli",
        "event",
        "consume",
        lark.get("event_key", "im.message.receive_v1"),
        "--as",
        lark.get("identity", "bot"),
    ]
    if max_events:
        cmd.extend(["--max-events", str(max_events)])
    if timeout:
        cmd.extend(["--timeout", timeout])

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    assert proc.stderr is not None

    ready = threading.Event()
    threading.Thread(target=_stderr_logger, args=(proc.stderr, ready), daemon=True).start()
    if not ready.wait(timeout=30):
        raise RuntimeError("lark-cli event consumer did not become ready within 30 seconds")

    print("[podcast2md] Feishu listener is ready.")
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                print(f"[podcast2md] skip non-json line: {line}", file=sys.stderr)
                continue
            added = handle_event(event, db_path, notifier)
            if added:
                print(f"[podcast2md] enqueued {added} task(s)")
    except KeyboardInterrupt:
        print("[podcast2md] stopping listener...")
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=10)


def main() -> None:
    parser = argparse.ArgumentParser(description="Listen to Feishu/Lark bot messages and enqueue URLs.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--max-events", type=int, default=0)
    parser.add_argument("--timeout", default=None)
    args = parser.parse_args()
    listen(args.config, max_events=args.max_events, timeout=args.timeout)


if __name__ == "__main__":
    main()
