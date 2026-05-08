from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
from podcast2md.config import ensure_paths, load_config
from podcast2md.db import init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize podcast2md queue database.")
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    ensure_paths(config)
    init_db(config["paths"]["queue_db"])
    print(f"Initialized queue database: {config['paths']['queue_db']}")


if __name__ == "__main__":
    main()
