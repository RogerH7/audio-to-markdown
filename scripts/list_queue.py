from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
from podcast2md.config import load_config
from podcast2md.db import list_tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="List recent queue tasks.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    config = load_config(args.config)
    rows = list_tasks(config["paths"]["queue_db"], limit=args.limit)
    for row in rows:
        print(
            f"#{row['id']} {row['status']:9s} {row['platform']:10s} "
            f"attempts={row['attempts']} url={row['url']} output={row['output_path'] or ''}"
        )


if __name__ == "__main__":
    main()
