from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from .config import load_config
from .db import enqueue_url
from .notifier import LarkNotifier
from .url_utils import extract_urls


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, dict):
        return content.get("text") or json.dumps(content, ensure_ascii=False)
    if not isinstance(content, str):
        return str(content)
    try:
        decoded = json.loads(content)
    except json.JSONDecodeError:
        return content
    if isinstance(decoded, dict):
        return decoded.get("text") or json.dumps(decoded, ensure_ascii=False)
    return content


def _messages_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "messages"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    data = payload.get("data")
    if isinstance(data, dict):
        return _messages_from_payload(data)
    return []


def poll_once(
    *,
    db_path: str | Path,
    chat_id: str,
    identity: str = "user",
    page_size: int = 20,
    notifier: LarkNotifier | None = None,
) -> int:
    cmd = [
        "lark-cli",
        "im",
        "+chat-messages-list",
        "--as",
        identity,
        "--chat-id",
        chat_id,
        "--sort",
        "desc",
        "--page-size",
        str(page_size),
        "--format",
        "json",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    messages = _messages_from_payload(payload)

    added = 0
    for message in reversed(messages):
        text = _message_text(message)
        urls = extract_urls(text)
        if not urls:
            continue
        message_id = message.get("message_id") or message.get("id")
        sender = message.get("sender_id") or message.get("sender", {}).get("id")
        for url in urls:
            task_id, created = enqueue_url(
                db_path,
                url,
                event_id=message_id,
                message_id=message_id,
                chat_id=message.get("chat_id") or chat_id,
                sender_id=sender,
                metadata={"raw_lark_message": message, "polling_identity": identity},
            )
            if created:
                added += 1
                if notifier:
                    notifier.reply(
                        message_id,
                        f"已加入转写队列：#{task_id}\n{url}",
                        idempotency_key=f"podcast2md-poll-enqueue-{task_id}",
                    )
    return added


def poll_loop(config_path: str, *, chat_id: str, identity: str, interval: int, once: bool) -> None:
    config = load_config(config_path)
    db_path = config["paths"]["queue_db"]
    lark = config.get("lark", {})
    notifier = None
    if identity == "bot" and lark.get("reply_enabled", True):
        notifier = LarkNotifier(enabled=True, identity="bot")

    while True:
        added = poll_once(
            db_path=db_path,
            chat_id=chat_id,
            identity=identity,
            notifier=notifier,
        )
        print(f"[lark-poll] enqueued {added} task(s)")
        if once:
            return
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll a Feishu/Lark chat as a fallback inbox.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--chat-id", required=True, help="Chat ID, usually starts with oc_")
    parser.add_argument("--as", dest="identity", default="user", choices=["user", "bot"])
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    poll_loop(args.config, chat_id=args.chat_id, identity=args.identity, interval=args.interval, once=args.once)


if __name__ == "__main__":
    main()
