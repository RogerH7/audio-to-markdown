from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests


class AsrProvider:
    def transcribe(self, audio_url: str) -> dict[str, Any]:
        raise NotImplementedError


class AliyunParaformerV2(AsrProvider):
    def __init__(self, options: dict[str, Any]) -> None:
        self.api_key_env = options.get("api_key_env", "DASHSCOPE_API_KEY")
        self.model = options.get("model", "paraformer-v2")
        self.language_hints = options.get("language_hints", ["zh", "en"])
        self.diarization_enabled = bool(options.get("diarization_enabled", True))
        self.timestamp_alignment_enabled = bool(options.get("timestamp_alignment_enabled", True))
        self.poll_interval_seconds = int(options.get("poll_interval_seconds", 5))
        self.max_wait_seconds = int(options.get("max_wait_seconds", 1800))

    def transcribe(self, audio_url: str) -> dict[str, Any]:
        import dashscope
        from dashscope.audio.asr import Transcription

        api_key = os.getenv(self.api_key_env, "")
        if not api_key:
            raise RuntimeError(f"Missing API key environment variable: {self.api_key_env}")
        dashscope.api_key = api_key

        response = Transcription.async_call(
            model=self.model,
            file_urls=[audio_url],
            language_hints=self.language_hints,
            diarization_enabled=self.diarization_enabled,
            timestamp_alignment_enabled=self.timestamp_alignment_enabled,
        )
        if getattr(response, "status_code", 200) != 200:
            raise RuntimeError(f"Failed to submit ASR task: {response}")

        task_id = response.output["task_id"]
        print(f"[asr] submitted Aliyun Paraformer task: {task_id}")
        started_at = time.monotonic()
        while True:
            if time.monotonic() - started_at > self.max_wait_seconds:
                raise TimeoutError(
                    f"ASR task {task_id} did not finish within {self.max_wait_seconds} seconds"
                )
            result = Transcription.fetch(task=task_id)
            if result.status_code != 200:
                raise RuntimeError(f"ASR polling failed: {result}")
            status = result.output.get("task_status") or result.output.get("status")
            elapsed = int(time.monotonic() - started_at)
            print(f"[asr] task {task_id} status={status} elapsed={elapsed}s")
            if status == "SUCCEEDED":
                results = result.output.get("results") or []
                if not results:
                    return result.output
                detail_url = results[0].get("transcription_url")
                if not detail_url:
                    return result.output
                print(f"[asr] downloading transcription result: {detail_url}")
                detail_resp = requests.get(detail_url, timeout=120)
                detail_resp.raise_for_status()
                detail = detail_resp.json()
                detail["_task_id"] = task_id
                return detail
            if status == "FAILED":
                raise RuntimeError(f"ASR task failed: {json.dumps(result.output, ensure_ascii=False)}")
            time.sleep(self.poll_interval_seconds)


class FixtureAsr(AsrProvider):
    def __init__(self, fixture_path: str | Path) -> None:
        self.fixture_path = Path(fixture_path)

    def transcribe(self, audio_url: str) -> dict[str, Any]:
        with self.fixture_path.open("r", encoding="utf-8") as f:
            return json.load(f)


def build_asr(config: dict[str, Any]) -> AsrProvider:
    asr = config.get("asr", {})
    provider = asr.get("provider", "aliyun_paraformer_v2")
    if provider == "aliyun_paraformer_v2":
        return AliyunParaformerV2(asr.get("aliyun_paraformer_v2", {}))
    if provider == "fixture":
        return FixtureAsr(asr.get("fixture_path", "data/asr_fixture.json"))
    raise ValueError(f"Unsupported ASR provider: {provider}")
