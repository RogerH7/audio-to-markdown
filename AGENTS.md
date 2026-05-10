# AGENTS.md

This file is for future AI/code agents working in this repository.

## Project

`audio2md` turns shared podcast/video links into Markdown notes.

Main workflow:

```text
Feishu Bot message
  -> lark event listener
  -> SQLite task queue
  -> worker downloads and normalizes audio
  -> Aliyun OSS temporary signed URL
  -> Aliyun Paraformer V2 ASR
  -> DeepSeek post-processing
  -> output/YYYY-MM-DD/*.md
  -> Feishu reply
```

## Repository Layout

- `src/podcast2md/`: application code.
- `scripts/`: CLI entry points; each script imports `scripts/_bootstrap.py`.
- `config/config.example.yaml`: safe committed config template.
- `config/config.yaml`: local private config, ignored by Git.
- `.env.example`: safe environment template.
- `.env`: local private secrets, ignored by Git.
- `docs/`: setup, workflow, cost, and GitHub upload docs.
- `data/`, `output/`, `logs/`: local runtime artifacts, ignored by Git.

## Important Commands

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Initialize queue:

```bash
python3 scripts/init_db.py
```

Check local config and OSS connectivity:

```bash
python3 scripts/check_config.py --network
```

Run the full always-on service:

```bash
python3 scripts/run_service.py
```

Process one queued task:

```bash
python3 scripts/run_worker.py --once
```

Run smoke checks:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/podcast2md_pycache python3 -m py_compile src/podcast2md/*.py scripts/*.py
python3 scripts/smoke_test.py
```

Inspect queue:

```bash
python3 scripts/list_queue.py --limit 10
```

Retry a failed task:

```bash
python3 scripts/retry_task.py <task-id>
```

Preview OSS cleanup:

```bash
python3 scripts/cleanup_storage.py --dry-run
```

## Development Rules

- Do not commit `.env`, `config/config.yaml`, cookies, `data/`, `output/`, `logs/`, ASR JSON, downloaded audio, or generated Markdown notes.
- Keep generated Markdown under `output/YYYY-MM-DD/`.
- Keep public documentation in sync when changing workflow behavior.
- Prefer config-driven behavior over hardcoded local paths.
- Preserve the phone-to-Feishu-to-worker flow; avoid adding a second intake mechanism unless it is clearly documented.
- For Bilibili/YouTube access fixes, use local config such as `cookies_from_browser: "chrome"` or `cookie_file`, but never commit cookies.
- Aliyun OSS should remain temporary storage. Current default is to retain temporary audio for 1 day and clean it later.
- The worker queue polling interval is configured by `service.worker_poll_interval_seconds`; Feishu event reception is long-connection based and should not be changed into polling unless necessary.

## Cost-Sensitive Defaults

- ASR model: `paraformer-v2`.
- LLM postprocess model: `deepseek-v4-flash`.
- OSS audio normalization: mono, 16 kHz, 64 kbps MP3.
- Output retention: Markdown output is local; OSS temporary audio is cleaned by retention policy.

## Code Notes

- `src/podcast2md/markdown.py` owns Markdown rendering and output path layout.
- `src/podcast2md/worker.py` owns the end-to-end task execution.
- `src/podcast2md/storage.py` owns OSS upload, signed URL generation, and cleanup.
- `src/podcast2md/asr.py` owns DashScope/Paraformer polling.
- `src/podcast2md/lark_listener.py` owns event consumption and URL enqueueing.
- `src/podcast2md/url_utils.py` owns URL extraction, normalization, platform detection, and de-duplication keys.

## Verification Expectations

Before committing code changes, run:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/podcast2md_pycache python3 -m py_compile src/podcast2md/*.py scripts/*.py
python3 scripts/smoke_test.py
git status --short --ignored
```

Expected ignored files include local secrets and runtime outputs. If `git status --short --ignored` shows `.env`, `config/config.yaml`, `data/`, or `output/` as tracked/staged, stop and fix `.gitignore` or staging scope before committing.

## GitHub

Remote:

```text
https://github.com/RogerH7/audio-to-markdown.git
```

Use small, descriptive commits. Do not push unverified changes that affect the ingestion or worker path.
