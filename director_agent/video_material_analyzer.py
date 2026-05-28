"""Analyze uploaded video materials from transcript and key-frame summaries."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping

from .config import PROJECT_ROOT, load_yaml_like


VIDEO_LIBRARY_DIR = PROJECT_ROOT / "references" / "video_library"
VIDEO_INDEX_PATH = VIDEO_LIBRARY_DIR / "index.json"
RULE_PATH = PROJECT_ROOT / "rules" / "video_analysis_rules.json"


def analyze_video_material(material: Mapping[str, Any]) -> Dict[str, Any]:
    rules = _load_rules()
    transcript = str(material.get("transcript") or material.get("manual_transcript") or "")
    sentences = _split_sentences(transcript)
    frame_summaries = list(material.get("frame_summaries") or [])
    category = str(material.get("category") or "通用类目")
    script_mode = str(material.get("script_mode") or "ai_video")

    return {
        "视频基础信息": {
            "视频标题": material.get("title", ""),
            "来源平台": material.get("platform", ""),
            "来源链接": material.get("source_url", ""),
            "产品类目": category,
            "关键帧数量": len(frame_summaries),
        },
        "口播/字幕转写": transcript or "未提供转写；请补充口播或字幕文案以提升分析准确度。",
        "开头3秒钩子": _first_sentence(sentences),
        "视频节奏拆解": _infer_rhythm(transcript, script_mode, rules),
        "场景设计": _infer_scenes(transcript, frame_summaries),
        "人物关系": _infer_persona(category, transcript),
        "用户痛点": _infer_pain(category, transcript),
        "剧情冲突": _infer_conflict(category, transcript),
        "产品出现时机": _infer_product_timing(transcript),
        "卖点植入方式": _infer_placement(transcript),
        "镜头/画面特点": _infer_visual_features(transcript, frame_summaries, rules),
        "字幕风格": _infer_subtitle_style(transcript),
        "情绪触发点": _infer_emotions(category),
        "转化引导方式": _infer_conversion(transcript, rules),
        "可模仿结构": _infer_rhythm(transcript, script_mode, rules),
        "不能照搬的表达": _avoid_expressions(sentences),
        "适合迁移到哪些产品": _suitable_products(category),
        "analysis_version": "v0.9-local",
    }


def save_video_material(material: Mapping[str, Any]) -> Dict[str, Any]:
    VIDEO_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    if not VIDEO_INDEX_PATH.exists():
        VIDEO_INDEX_PATH.write_text("[]\n", encoding="utf-8")

    item = dict(material)
    if not item.get("id"):
        item["id"] = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    if not item.get("created_at"):
        item["created_at"] = datetime.now().isoformat(timespec="seconds")
    if not item.get("analysis_result"):
        item["analysis_result"] = analyze_video_material(item)

    item_path = VIDEO_LIBRARY_DIR / f"{item['id']}.json"
    item_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        index = json.loads(VIDEO_INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        index = []
    index = [existing for existing in index if existing.get("id") != item["id"]]
    index.insert(0, _index_record(item))
    VIDEO_INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return item


def load_video_library() -> List[Dict[str, Any]]:
    VIDEO_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    if not VIDEO_INDEX_PATH.exists():
        VIDEO_INDEX_PATH.write_text("[]\n", encoding="utf-8")
    try:
        data = json.loads(VIDEO_INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _index_record(item: Mapping[str, Any]) -> Dict[str, Any]:
    analysis = item.get("analysis_result") if isinstance(item.get("analysis_result"), dict) else {}
    return {
        "id": item.get("id", ""),
        "title": item.get("title", ""),
        "platform": item.get("platform", ""),
        "source_url": item.get("source_url", ""),
        "category": item.get("category", ""),
        "transcript": item.get("transcript", ""),
        "frame_paths": item.get("frame_paths", []),
        "analysis_summary": {
            "开头3秒钩子": analysis.get("开头3秒钩子", ""),
            "视频节奏拆解": analysis.get("视频节奏拆解", ""),
            "转化引导方式": analysis.get("转化引导方式", ""),
        },
        "created_at": item.get("created_at", ""),
    }


def _load_rules() -> Dict[str, Any]:
    return load_yaml_like(RULE_PATH) if RULE_PATH.exists() else {}


def _split_sentences(text: str) -> List[str]:
    chunks = re.split(r"[\n。！？!?；;]+", text)
    return [chunk.strip(" ，,：:") for chunk in chunks if chunk.strip()]


def _first_sentence(sentences: List[str]) -> str:
    return sentences[0][:90] if sentences else "用前三秒明确抛出场景矛盾或用户痛点"


def _infer_rhythm(transcript: str, script_mode: str, rules: Mapping[str, Any]) -> str:
    patterns = rules.get("rhythm_patterns") or {}
    if "对比" in transcript or "之前" in transcript:
        return "反差开场 -> 使用前问题 -> 产品介入 -> 使用后反馈 -> 行动引导"
    return str(patterns.get(script_mode) or "钩子 -> 冲突 -> 产品 -> 证明 -> 转化")


def _infer_scenes(transcript: str, frame_summaries: List[str]) -> List[str]:
    candidates = ["浴室", "通勤前", "后厨", "工厂", "客厅", "办公室", "厨房", "门店", "梳妆台"]
    scenes = [item for item in candidates if item in transcript]
    if frame_summaries:
        scenes.append("关键帧画面可辅助判断场景")
    return scenes[:4] or ["真实使用场景"]


def _infer_persona(category: str, transcript: str) -> str:
    if "老板" in transcript or category == "冻品餐饮类":
        return "老板与执行者"
    if "宝妈" in transcript or category == "母婴纸品类":
        return "宝妈与家庭成员"
    if "闺蜜" in transcript:
        return "闺蜜与女主"
    return "种草者与目标用户"


def _infer_pain(category: str, transcript: str) -> str:
    if "扁塌" in transcript or "头发" in transcript:
        return "用户担心状态不好、使用体验不够直观"
    if "出餐" in transcript or "后厨" in transcript:
        return "高峰期效率和稳定出品压力"
    return f"{category}用户需要被具体场景和细节说服"


def _infer_conflict(category: str, transcript: str) -> str:
    if "没想到" in transcript or "但是" in transcript:
        return "预期和实际体验之间形成反差"
    return f"用户痛点被放大后，产品需要以自然方式解决{category}场景里的问题"


def _infer_product_timing(transcript: str) -> str:
    if "先别急" in transcript:
        return "先抛出问题，再让产品在解决方案阶段出现"
    return "开头建立痛点，中段产品出现，结尾定格产品和行动理由"


def _infer_placement(transcript: str) -> str:
    if "测评" in transcript or "实测" in transcript:
        return "通过演示和对比完成卖点证明"
    return "产品跟随人物动作自然出现，承接痛点解决过程"


def _infer_visual_features(transcript: str, frame_summaries: List[str], rules: Mapping[str, Any]) -> List[str]:
    keywords = rules.get("visual_keywords") or []
    found = [item for item in keywords if item in transcript]
    if frame_summaries:
        found.append("关键帧抽取用于辅助画面节奏判断")
    return found[:5] or ["近景表情", "产品特写", "字幕强化信息"]


def _infer_subtitle_style(transcript: str) -> str:
    if len(transcript) > 120:
        return "短句分行、重点词前置，适合短视频快节奏阅读"
    return "强钩子短字幕，突出痛点和行动提示"


def _infer_emotions(category: str) -> List[str]:
    if category == "冻品餐饮类":
        return ["高峰压力", "效率反转", "老板安心"]
    if category == "母婴纸品类":
        return ["照顾细节", "家庭安心", "温柔陪伴"]
    return ["痛点共鸣", "状态反差", "被说服后的行动冲动"]


def _infer_conversion(transcript: str, rules: Mapping[str, Any]) -> str:
    for keyword in rules.get("conversion_keywords", []):
        if keyword in transcript:
            return "用收藏、评论、咨询或查看链接承接兴趣"
    return "用低门槛动作收束，例如收藏、咨询、对照需求选择"


def _avoid_expressions(sentences: List[str]) -> List[str]:
    return [sentence[:42] for sentence in sentences if len(sentence) >= 10][:5] or ["原视频完整句子、品牌名、人名和专属剧情细节不能照搬"]


def _suitable_products(category: str) -> List[str]:
    return [f"{category}同类产品", "同人群同场景产品", "可用相似转化逻辑表达的电商产品"]
