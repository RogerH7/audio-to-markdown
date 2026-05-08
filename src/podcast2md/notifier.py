from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class LarkNotifier:
    enabled: bool = True
    identity: str = "bot"
    reply_in_thread: bool = True

    def reply(self, message_id: str | None, text: str, *, idempotency_key: str | None = None) -> None:
        if not self.enabled or not message_id:
            return

        cmd = [
            "lark-cli",
            "im",
            "+messages-reply",
            "--as",
            self.identity,
            "--message-id",
            message_id,
            "--text",
            text,
        ]
        if self.reply_in_thread:
            cmd.append("--reply-in-thread")
        if idempotency_key:
            cmd.extend(["--idempotency-key", idempotency_key])

        subprocess.run(cmd, check=False, capture_output=True, text=True)
