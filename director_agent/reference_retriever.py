"""Read, write, and filter manually collected reference copy materials."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .config import PROJECT_ROOT
from .copy_analyzer import analyze_reference_copy
from .llm import LLMClient


COPY_LIBRARY_DIR = PROJECT_ROOT / "references" / "copy_library"
INDEX_PATH = COPY_LIBRARY_DIR / "index.json"


def ensure_copy_library() -> None:
    COPY_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        INDEX_PATH.write_text("[]\n", encoding="utf-8")


def load_copy_library() -> List[Dict[str, Any]]:
    ensure_copy_library()
    try:
        data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def add_reference_material(
    *,
    title: str,
    platform: str,
    source_url: str,
    category: str,
    content_type: str,
    original_copy: str,
    engagement_data: str = "",
    user_note: str = "",
    analyze: bool = True,
    settings: Optional[Dict[str, Any]] = None,
    llm_client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    reference = {
        "id": _new_reference_id(),
        "title": title.strip(),
        "platform": platform.strip(),
        "source_url": source_url.strip(),
        "category": category.strip(),
        "content_type": content_type.strip(),
        "original_copy": original_copy.strip(),
        "engagement_data": engagement_data.strip(),
        "user_note": user_note.strip(),
        "analysis_result": {},
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    if analyze:
        reference["analysis_result"] = analyze_reference_copy(reference, settings=settings, llm_client=llm_client)
    save_reference_material(reference, settings=settings, llm_client=llm_client)
    return reference


def save_reference_material(
    reference: Mapping[str, Any],
    settings: Optional[Dict[str, Any]] = None,
    llm_client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    ensure_copy_library()
    item = dict(reference)
    if not item.get("id"):
        item["id"] = _new_reference_id()
    if not item.get("created_at"):
        item["created_at"] = datetime.now().isoformat(timespec="seconds")
    if not item.get("analysis_result"):
        item["analysis_result"] = analyze_reference_copy(item, settings=settings, llm_client=llm_client)

    item_path = COPY_LIBRARY_DIR / f"{item['id']}.json"
    item_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")

    index = [existing for existing in load_copy_library() if existing.get("id") != item["id"]]
    index.insert(0, _index_record(item))
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return item


def get_reference_material(reference_id: str) -> Optional[Dict[str, Any]]:
    ensure_copy_library()
    item_path = COPY_LIBRARY_DIR / f"{reference_id}.json"
    if not item_path.exists():
        return None
    try:
        data = json.loads(item_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def select_reference_materials(reference_ids: Iterable[str]) -> List[Dict[str, Any]]:
    selected = []
    for reference_id in reference_ids:
        item = get_reference_material(str(reference_id))
        if item:
            selected.append(item)
    return selected[:5]


def find_related_references(category: str = "", content_type: str = "", limit: int = 5) -> List[Dict[str, Any]]:
    records = load_copy_library()
    scored = []
    for item in records:
        score = 0
        if category and item.get("category") == category:
            score += 2
        if content_type and item.get("content_type") == content_type:
            score += 1
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:limit]]


def _index_record(item: Mapping[str, Any]) -> Dict[str, Any]:
    analysis = item.get("analysis_result") if isinstance(item.get("analysis_result"), dict) else {}
    return {
        "id": item.get("id", ""),
        "title": item.get("title", ""),
        "platform": item.get("platform", ""),
        "source_url": item.get("source_url", ""),
        "category": item.get("category", ""),
        "content_type": item.get("content_type", ""),
        "engagement_data": item.get("engagement_data", ""),
        "user_note": item.get("user_note", ""),
        "analysis_summary": {
            "开头钩子": analysis.get("开头钩子", ""),
            "内容结构": analysis.get("内容结构", ""),
            "转化引导方式": analysis.get("转化引导方式", ""),
        },
        "created_at": item.get("created_at", ""),
    }


def _new_reference_id() -> str:
    return f"ref_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
