from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import _bootstrap  # noqa: F401
from podcast2md.config import load_config


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Feishu listener and worker together.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--worker-poll-interval", type=int, default=None)
    parser.add_argument("--storage-cleanup-interval", type=int, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    service_cfg = config.get("service", {})
    storage_cfg = config.get("storage", {})
    worker_poll_interval = int(
        args.worker_poll_interval
        or service_cfg.get("worker_poll_interval_seconds", 30)
        or 30
    )
    retention_days = int(storage_cfg.get("retention_days", 0) or 0)
    cleanup_interval = int(
        args.storage_cleanup_interval
        or storage_cfg.get("cleanup_interval_seconds", 3600)
        or 3600
    )

    commands = [
        [
            sys.executable,
            str(ROOT / "scripts" / "listen_lark.py"),
            "--config",
            args.config,
        ],
        [
            sys.executable,
            str(ROOT / "scripts" / "run_worker.py"),
            "--config",
            args.config,
            "--poll-interval",
            str(worker_poll_interval),
        ],
    ]
    if retention_days > 0:
        commands.append(
            [
                sys.executable,
                str(ROOT / "scripts" / "cleanup_storage.py"),
                "--config",
                args.config,
                "--loop",
                "--interval",
                str(cleanup_interval),
            ]
        )
    procs: list[subprocess.Popen] = []
    try:
        for cmd in commands:
            proc = subprocess.Popen(cmd, cwd=str(ROOT))
            procs.append(proc)
            print(f"[service] started pid={proc.pid}: {' '.join(cmd)}")

        while True:
            for proc in procs:
                code = proc.poll()
                if code is not None:
                    raise RuntimeError(f"subprocess exited pid={proc.pid} code={code}")
            time.sleep(2)
    except KeyboardInterrupt:
        print("[service] stopping...")
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
