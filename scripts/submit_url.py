from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
from podcast2md.config import ensure_paths, load_config
from podcast2md.db import enqueue_url, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Manually enqueue one URL.")
    parser.add_argument("url")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--note", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    ensure_paths(config)
    init_db(config["paths"]["queue_db"])
    task_id, created = enqueue_url(config["paths"]["queue_db"], args.url, note=args.note)
    status = "created" if created else "already exists"
    print(f"Task #{task_id}: {status}")


if __name__ == "__main__":
    main()
