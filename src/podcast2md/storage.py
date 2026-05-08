from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class UploadedObject:
    public_url: str
    object_key: str | None = None


class StorageProvider:
    def upload(self, path: str | Path) -> UploadedObject:
        raise NotImplementedError

    def delete(self, object_key: str) -> None:
        raise NotImplementedError

    def delete_older_than(self, cutoff_epoch_seconds: int, *, dry_run: bool = False) -> list[dict[str, Any]]:
        return []


@dataclass
class AliyunOssStorage(StorageProvider):
    endpoint: str
    bucket: str
    access_key_id_env: str
    access_key_secret_env: str
    prefix: str = "podcast2md/audio"
    signed_url_expires_seconds: int = 86400

    def upload(self, path: str | Path) -> UploadedObject:
        import oss2

        path = Path(path)
        access_key_id = os.getenv(self.access_key_id_env, "")
        access_key_secret = os.getenv(self.access_key_secret_env, "")
        if not access_key_id or not access_key_secret:
            raise RuntimeError(
                f"Missing OSS credentials: {self.access_key_id_env}/{self.access_key_secret_env}"
            )
        if not self.endpoint or not self.bucket:
            raise RuntimeError("Missing OSS endpoint or bucket in config.")

        auth = oss2.Auth(access_key_id, access_key_secret)
        bucket = oss2.Bucket(auth, self.endpoint, self.bucket)
        key = f"{self.prefix.strip('/')}/{path.name}"
        bucket.put_object_from_file(key, str(path))
        url = bucket.sign_url("GET", key, self.signed_url_expires_seconds)
        return UploadedObject(public_url=url, object_key=key)

    def delete(self, object_key: str) -> None:
        import oss2

        access_key_id = os.getenv(self.access_key_id_env, "")
        access_key_secret = os.getenv(self.access_key_secret_env, "")
        if not access_key_id or not access_key_secret:
            raise RuntimeError(
                f"Missing OSS credentials: {self.access_key_id_env}/{self.access_key_secret_env}"
            )
        auth = oss2.Auth(access_key_id, access_key_secret)
        bucket = oss2.Bucket(auth, self.endpoint, self.bucket)
        bucket.delete_object(object_key)

    def delete_older_than(self, cutoff_epoch_seconds: int, *, dry_run: bool = False) -> list[dict[str, Any]]:
        import oss2

        access_key_id = os.getenv(self.access_key_id_env, "")
        access_key_secret = os.getenv(self.access_key_secret_env, "")
        if not access_key_id or not access_key_secret:
            raise RuntimeError(
                f"Missing OSS credentials: {self.access_key_id_env}/{self.access_key_secret_env}"
            )

        auth = oss2.Auth(access_key_id, access_key_secret)
        bucket = oss2.Bucket(auth, self.endpoint, self.bucket)
        deleted: list[dict[str, Any]] = []
        prefix = self.prefix.strip("/")
        for obj in oss2.ObjectIterator(bucket, prefix=f"{prefix}/"):
            last_modified = int(getattr(obj, "last_modified", 0) or 0)
            if last_modified >= cutoff_epoch_seconds:
                continue
            record = {
                "object_key": obj.key,
                "last_modified": last_modified,
                "size": int(getattr(obj, "size", 0) or 0),
            }
            if not dry_run:
                bucket.delete_object(obj.key)
            deleted.append(record)
        return deleted


@dataclass
class PublicBaseUrlStorage(StorageProvider):
    """Use when another process already exposes a local directory over HTTPS."""

    public_base_url: str

    def upload(self, path: str | Path) -> UploadedObject:
        path = Path(path)
        base = self.public_base_url.rstrip("/")
        return UploadedObject(public_url=f"{base}/{path.name}", object_key=path.name)

    def delete(self, object_key: str) -> None:
        return None


def build_storage(config: dict) -> StorageProvider:
    storage = config.get("storage", {})
    provider = storage.get("provider", "aliyun_oss")
    if provider == "aliyun_oss":
        opts = storage.get("aliyun_oss", {})
        return AliyunOssStorage(
            endpoint=opts.get("endpoint", ""),
            bucket=opts.get("bucket", ""),
            access_key_id_env=opts.get("access_key_id_env", "ALIYUN_ACCESS_KEY_ID"),
            access_key_secret_env=opts.get("access_key_secret_env", "ALIYUN_ACCESS_KEY_SECRET"),
            prefix=opts.get("prefix", "podcast2md/audio"),
            signed_url_expires_seconds=int(opts.get("signed_url_expires_seconds", 86400)),
        )
    if provider == "public_base_url":
        return PublicBaseUrlStorage(storage.get("public_base_url", ""))
    raise ValueError(f"Unsupported storage provider: {provider}")
