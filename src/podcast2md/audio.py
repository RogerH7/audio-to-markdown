from __future__ import annotations

import subprocess
from pathlib import Path


def normalize_audio(input_path: str | Path, output_dir: str | Path) -> Path:
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{input_path.stem}.mono.mp3"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "64k",
        str(target),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return target
