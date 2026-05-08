from __future__ import annotations

import argparse
import os
import sys

import _bootstrap  # noqa: F401
from podcast2md.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="List recent Aliyun DashScope ASR tasks.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--status", default=None)
    parser.add_argument("--page-size", type=int, default=10)
    args = parser.parse_args()

    config = load_config(args.config)
    asr_opts = config.get("asr", {}).get("aliyun_paraformer_v2", {})
    api_key_env = asr_opts.get("api_key_env", "DASHSCOPE_API_KEY")
    api_key = os.getenv(api_key_env, "")
    if not api_key:
        raise SystemExit(f"Missing {api_key_env}")

    from dashscope.audio.asr import Transcription

    response = Transcription.list(
        model_name=asr_opts.get("model", "paraformer-v2"),
        status=args.status,
        page_size=args.page_size,
        api_key=api_key,
    )
    if response.status_code != 200:
        print(response, file=sys.stderr)
        raise SystemExit(1)
    print(response.output)


if __name__ == "__main__":
    main()
