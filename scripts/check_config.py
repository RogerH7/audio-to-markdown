from __future__ import annotations

import argparse
import importlib
import os
import re
import requests
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401
from podcast2md.config import load_config
from podcast2md.storage import build_storage


REQUIRED_ENV = [
    "DASHSCOPE_API_KEY",
    "DEEPSEEK_API_KEY",
    "ALIYUN_ACCESS_KEY_ID",
    "ALIYUN_ACCESS_KEY_SECRET",
    "ALIYUN_OSS_ENDPOINT",
    "ALIYUN_OSS_BUCKET",
]

REQUIRED_MODULES = ["dashscope", "openai", "oss2", "yt_dlp", "yaml"]


def _masked(value: str) -> str:
    if not value:
        return "missing"
    if len(value) <= 8:
        return "configured"
    return f"{value[:4]}...{value[-4:]}"


def check_env(config: dict) -> bool:
    ok = True
    values = {
        "DASHSCOPE_API_KEY": config.get("asr", {})
        .get("aliyun_paraformer_v2", {})
        .get("api_key_env", "DASHSCOPE_API_KEY"),
        "DEEPSEEK_API_KEY": config.get("postprocess", {})
        .get("deepseek", {})
        .get("api_key_env", "DEEPSEEK_API_KEY"),
        "ALIYUN_ACCESS_KEY_ID": "ALIYUN_ACCESS_KEY_ID",
        "ALIYUN_ACCESS_KEY_SECRET": "ALIYUN_ACCESS_KEY_SECRET",
        "ALIYUN_OSS_ENDPOINT": "ALIYUN_OSS_ENDPOINT",
        "ALIYUN_OSS_BUCKET": "ALIYUN_OSS_BUCKET",
    }

    import os

    print("Environment")
    for label, env_name in values.items():
        value = os.getenv(env_name, "")
        status = "ok" if value else "missing"
        print(f"  {label:28s} {status:8s} {_masked(value)}")
        ok = ok and bool(value)
    bucket = os.getenv("ALIYUN_OSS_BUCKET", "")
    if bucket and not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket):
        print(
            "  ALIYUN_OSS_BUCKET            invalid  "
            "use only the bucket name, not a URL/domain"
        )
        ok = False
    endpoint = os.getenv("ALIYUN_OSS_ENDPOINT", "")
    if endpoint and not endpoint.startswith(("http://", "https://")):
        print("  ALIYUN_OSS_ENDPOINT          invalid  should start with https://")
        ok = False
    return ok


def check_imports() -> bool:
    ok = True
    print("Dependencies")
    for module in REQUIRED_MODULES:
        try:
            importlib.import_module(module)
            print(f"  {module:28s} ok")
        except Exception as exc:
            print(f"  {module:28s} missing  {type(exc).__name__}: {exc}")
            ok = False
    return ok


def check_oss(config: dict) -> bool:
    print("OSS")
    try:
        storage = build_storage(config)
        bucket = getattr(storage, "bucket", "")
        endpoint = getattr(storage, "endpoint", "")
        print(f"  endpoint                     {endpoint or 'missing'}")
        print(f"  bucket                       {bucket or 'missing'}")
        if storage.__class__.__name__ == "AliyunOssStorage":
            import oss2

            access_key_id = os.getenv(storage.access_key_id_env, "")
            access_key_secret = os.getenv(storage.access_key_secret_env, "")
            auth = oss2.Auth(access_key_id, access_key_secret)
            oss_bucket = oss2.Bucket(auth, endpoint, bucket)
            try:
                info = oss_bucket.get_bucket_info()
                print(f"  get-bucket-info              ok  storage_class={info.storage_class}")
            except Exception as exc:
                print(f"  get-bucket-info              failed  {type(exc).__name__}: {exc}")

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("audio2md config check\n")
            temp_path = Path(f.name)
        try:
            uploaded = storage.upload(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)
        print(f"  upload/sign-url              ok  object={uploaded.object_key}")
        try:
            response = requests.get(uploaded.public_url, timeout=20)
            response.raise_for_status()
            print(f"  signed-url-get               ok  bytes={len(response.content)}")
        except Exception as exc:
            print(f"  signed-url-get               failed  {type(exc).__name__}: {exc}")
            return False
        return True
    except Exception as exc:
        print(f"  upload/sign-url              failed  {type(exc).__name__}: {exc}")
        message = str(exc)
        if "AccessDenied" in message:
            print("  hint                         AccessKey has no OSS permission for this bucket, or belongs to another Alibaba Cloud account.")
            print("  required                     oss:PutObject and oss:GetObject on bucket and objects")
        if "NoSuchBucket" in message:
            print("  hint                         Check bucket name and endpoint region.")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Check local config without printing secrets.")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--network", action="store_true", help="Also test OSS upload/sign-url.")
    args = parser.parse_args()

    config = load_config(args.config)
    ok = check_env(config)
    ok = check_imports() and ok
    if args.network:
        ok = check_oss(config) and ok
    if not ok:
        raise SystemExit(1)
    print("config check passed")


if __name__ == "__main__":
    main()
