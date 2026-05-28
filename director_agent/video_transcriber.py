"""Video transcription adapter with manual transcript fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def transcribe_video(video_path: Path | None = None, manual_transcript: str = "") -> Dict[str, Any]:
    """Return manual transcript first; never block the video analysis flow."""

    manual_transcript = (manual_transcript or "").strip()
    if manual_transcript:
        return {
            "transcript": manual_transcript,
            "source": "manual",
            "note": "使用用户手动补充的口播/字幕文案。",
        }

    return {
        "transcript": "",
        "source": "none",
        "note": "当前环境未配置自动转写服务，请补充口播或字幕文案后再分析。",
    }
