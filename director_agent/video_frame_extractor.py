"""Best-effort key frame extraction for uploaded video materials."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import PROJECT_ROOT


FRAME_DIR = PROJECT_ROOT / "references" / "video_library" / "frames"
TEMP_DIR = PROJECT_ROOT / "temp"


def extract_keyframes(
    video_path: Path,
    output_dir: Optional[Path] = None,
    interval_seconds: int = 3,
    max_frames: int = 12,
) -> Dict[str, Any]:
    """Extract key frames without making extraction mandatory for the flow."""

    output_dir = output_dir or FRAME_DIR / uuid.uuid4().hex[:10]
    output_dir.mkdir(parents=True, exist_ok=True)
    interval_seconds = max(1, int(interval_seconds or 3))
    max_frames = max(1, int(max_frames or 12))

    if not video_path or not Path(video_path).exists():
        return _empty_result("video file does not exist")

    cv2_result = _extract_with_cv2(Path(video_path), output_dir, interval_seconds, max_frames)
    if cv2_result["frame_paths"]:
        return cv2_result

    ffmpeg_result = _extract_with_ffmpeg(Path(video_path), output_dir, interval_seconds, max_frames)
    if ffmpeg_result["frame_paths"]:
        return ffmpeg_result

    return _empty_result("no frame extraction backend available")


def save_uploaded_video_temporarily(uploaded_file: Any, suffix: str = ".mp4") -> Path:
    """Save Streamlit uploaded bytes to a temp path; caller may delete it later."""

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    name = getattr(uploaded_file, "name", "") or f"uploaded{suffix}"
    extension = Path(name).suffix or suffix
    target = TEMP_DIR / f"uploaded_{uuid.uuid4().hex[:10]}{extension}"
    data = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
    target.write_bytes(data)
    return target


def summarize_frames(frame_paths: List[str]) -> List[str]:
    summaries = []
    for index, path in enumerate(frame_paths, start=1):
        summaries.append(f"关键帧{index}：已抽取画面文件 {Path(path).name}，用于人工预览和结构判断。")
    return summaries


def _extract_with_cv2(video_path: Path, output_dir: Path, interval_seconds: int, max_frames: int) -> Dict[str, Any]:
    try:
        import cv2  # type: ignore
    except Exception:
        return _empty_result("opencv unavailable")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return _empty_result("opencv cannot open video")

    fps = capture.get(cv2.CAP_PROP_FPS) or 25
    frame_interval = max(1, int(fps * interval_seconds))
    frame_paths: List[str] = []
    frame_index = 0
    saved_index = 0
    while len(frame_paths) < max_frames:
        success, frame = capture.read()
        if not success:
            break
        if frame_index % frame_interval == 0:
            saved_index += 1
            frame_path = output_dir / f"frame_{saved_index:02d}.jpg"
            cv2.imwrite(str(frame_path), frame)
            frame_paths.append(str(frame_path))
        frame_index += 1
    capture.release()
    return {
        "frame_paths": frame_paths,
        "frame_summaries": summarize_frames(frame_paths),
        "backend": "opencv",
        "note": "" if frame_paths else "opencv extracted no frames",
    }


def _extract_with_ffmpeg(video_path: Path, output_dir: Path, interval_seconds: int, max_frames: int) -> Dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return _empty_result("ffmpeg unavailable")

    pattern = output_dir / "frame_%02d.jpg"
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps=1/{interval_seconds}",
        "-vframes",
        str(max_frames),
        str(pattern),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    except Exception as exc:
        return _empty_result(f"ffmpeg failed: {exc}")

    frame_paths = [str(path) for path in sorted(output_dir.glob("frame_*.jpg"))[:max_frames]]
    return {
        "frame_paths": frame_paths,
        "frame_summaries": summarize_frames(frame_paths),
        "backend": "ffmpeg",
        "note": "" if frame_paths else "ffmpeg extracted no frames",
    }


def _empty_result(note: str) -> Dict[str, Any]:
    return {"frame_paths": [], "frame_summaries": [], "backend": "none", "note": note}
