from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import _bootstrap  # noqa: F401
from podcast2md.config import load_config
from podcast2md.storage import build_storage


def cleanup_once(config: dict[str, Any], *, dry_run: bool = False) -> int:
    storage_cfg = config.get("storage", {})
    retention_days = int(storage_cfg.get("retention_days", 0) or 0)
    if retention_days <= 0:
        print("[storage-cleanup] disabled because storage.retention_days <= 0")
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_epoch_seconds = int(cutoff.timestamp())
    storage = build_storage(config)
    deleted = storage.delete_older_than(cutoff_epoch_seconds, dry_run=dry_run)
    action = "would delete" if dry_run else "deleted"
    print(
        f"[storage-cleanup] retention_days={retention_days} "
        f"cutoff={cutoff.isoformat(timespec='seconds')} {action}={len(deleted)}"
    )
    for item in deleted[:20]:
        print(
            "[storage-cleanup] "
            f"{action} object={item['object_key']} size={item['size']} "
            f"last_modified={item['last_modified']}"
        )
    if len(deleted) > 20:
        print(f"[storage-cleanup] ... {len(deleted) - 20} more")
    return len(deleted)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean temporary audio objects from object storage.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    interval = int(
        args.interval
        or config.get("storage", {}).get("cleanup_interval_seconds", 3600)
        or 3600
    )

    while True:
        try:
            cleanup_once(config, dry_run=args.dry_run)
        except Exception as exc:
            if not args.loop:
                raise
            print(f"[storage-cleanup] warning: {type(exc).__name__}: {exc}")
        if not args.loop:
            return
        time.sleep(interval)


if __name__ == "__main__":
    main()
