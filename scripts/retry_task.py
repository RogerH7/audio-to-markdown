from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
from podcast2md.config import load_config
from podcast2md.db import retry_task


def main() -> None:
    parser = argparse.ArgumentParser(description="Put a failed task back into the retry queue.")
    parser.add_argument("task_id", type=int)
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    retry_task(config["paths"]["queue_db"], args.task_id)
    print(f"Task #{args.task_id} marked as retry.")


if __name__ == "__main__":
    main()
