"""Analyze uploaded video materials from transcript and key-frame summaries."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .config import PROJECT_ROOT, load_yaml_like
from .llm import LLMClient, resolve_llm_client


VIDEO_LIBRARY_DIR = PROJECT_ROOT / "references" / "video_library"
VIDEO_INDEX_PATH = VIDEO_LIBRARY_DIR / "index.json"
RULE_PATH = PROJECT_ROOT / "rules" / "video_analysis_rules.json"


def analyze_video_material(
    material: Mapping[str, Any],
    settings: Optional[Dict[str, Any]] = None,
    llm_client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    local_result = _analyze_video_material_local(material)
    evidence = _evidence_profile(material)
    if evidence["分析可信度"] == "不可分析":
        local_result["metadata"] = _analysis_metadata(
            "not_analyzable",
            provider="local",
            model="local",
            fallback_reason="未提取到关键帧，也未提供口播/字幕文案或画面摘要",
            frame_extraction_error=_frame_extraction_error(material),
        )
        local_result["metadata"].update(_evidence_metadata(material))
        return local_result
    if evidence["分析可信度"] == "低":
        local_result["metadata"] = _analysis_metadata(
            "low_confidence_local",
            provider="local",
            model="local",
            fallback_reason="仅有标题/类目或无视觉内容摘要，已禁止生成细节化剧情分析",
            frame_extraction_error=_frame_extraction_error(material),
        )
        local_result["metadata"].update(_evidence_metadata(material))
        return local_result
    if settings is None and llm_client is None:
        local_result["metadata"] = _analysis_metadata(
            "local_rules",
            provider="local",
            model="local",
            frame_extraction_error=_frame_extraction_error(material),
        )
        local_result["metadata"].update(_evidence_metadata(material))
        return local_result

    client, resolve_error = resolve_llm_client(settings=settings, llm_client=llm_client)
    if client is None:
        local_result["metadata"] = _analysis_metadata(
            "local_fallback",
            provider="local",
            model="local",
            fallback_reason=resolve_error or "LLM provider is local",
            frame_extraction_error=_frame_extraction_error(material),
        )
        local_result["metadata"].update(_evidence_metadata(material))
        return local_result

    provider = getattr(client, "provider_name", "unknown")
    model = getattr(client, "model", "unknown")
    try:
        payload = client.generate(_video_analysis_messages(material, local_result), _video_analysis_schema())
        result = _merge_video_analysis(local_result, payload)
        _reject_unsupported_hallucinations(material, result)
        result["metadata"] = _analysis_metadata(
            "llm",
            provider=provider,
            model=model,
            frame_extraction_error=_frame_extraction_error(material),
        )
        result["metadata"].update(_evidence_metadata(material))
        return result
    except Exception as exc:
        local_result["metadata"] = _analysis_metadata(
            "local_fallback",
            provider=provider,
            model=model,
            fallback_reason=str(exc),
            frame_extraction_error=_frame_extraction_error(material),
        )
        local_result["metadata"].update(_evidence_metadata(material))
        return local_result


def _analyze_video_material_local(material: Mapping[str, Any]) -> Dict[str, Any]:
    rules = _load_rules()
    transcript = _evidence_text(material)
    sentences = _split_sentences(transcript)
    evidence = _evidence_profile(material)
    frame_summaries = list(material.get("frame_summaries") or [])
    category = str(material.get("category") or "通用类目")
    script_mode = str(material.get("script_mode") or "ai_video")
    if evidence["分析可信度"] in {"不可分析", "低"}:
        message = "当前无法分析视频内容：未提取到关键帧，也未提供口播/字幕文案。请重新上传可读取的视频，或补充口播/字幕文案。"
        if evidence["分析可信度"] == "低":
            message = "当前只有标题/类目或关键帧文件路径，没有可识别的画面摘要或口播/字幕；已停止生成具体剧情分析。"
        return {
            "视频基础信息": {
                "视频标题": material.get("title", ""),
                "来源平台": material.get("platform", ""),
                "来源链接": material.get("source_url", ""),
                "产品类目": category,
                "关键帧数量": evidence["可用证据"]["keyframe_count"],
            },
            "可用证据": evidence["可用证据"],
            "分析可信度": evidence["分析可信度"],
            "口播/字幕转写": "未提供转写",
            "关键帧摘要": frame_summaries or ["未识别到"],
            "开头3秒钩子": "未识别到",
            "视频节奏拆解": message,
            "场景设计": ["未识别到"],
            "人物关系": "未识别到",
            "用户痛点": "未识别到",
            "剧情冲突": "未识别到",
            "产品出现时机": "未识别到",
            "卖点植入方式": "未识别到",
            "镜头/画面特点": ["未识别到"],
            "字幕风格": "未识别到",
            "情绪触发点": ["未识别到"],
            "转化引导方式": "未识别到",
            "可模仿结构": "未识别到",
            "不能照搬的表达": ["未识别到"],
            "适合迁移到哪些产品": ["未识别到"],
            "analysis_version": "v0.9-evidence-gated",
        }

    return {
        "视频基础信息": {
            "视频标题": material.get("title", ""),
            "来源平台": material.get("platform", ""),
            "来源链接": material.get("source_url", ""),
            "产品类目": category,
            "关键帧数量": evidence["可用证据"]["keyframe_count"],
        },
        "可用证据": evidence["可用证据"],
        "分析可信度": evidence["分析可信度"],
        "口播/字幕转写": transcript or "未提供转写；请补充口播或字幕文案以提升分析准确度。",
        "关键帧摘要": frame_summaries or ["未识别到"],
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


def _video_analysis_messages(material: Mapping[str, Any], local_result: Mapping[str, Any]) -> List[Dict[str, str]]:
    evidence = _evidence_profile(material)
    compact_material = {
        "title": material.get("title", ""),
        "platform": material.get("platform", ""),
        "source_url": material.get("source_url", ""),
        "category": material.get("category", ""),
        "script_mode": material.get("script_mode", ""),
        "available_evidence": evidence,
        "transcript": str(material.get("transcript") or material.get("manual_transcript") or "")[:4000],
        "supplemental_copy": str(material.get("supplemental_copy") or material.get("manual_frame_summary") or "")[:3000],
        "frame_summaries": list(material.get("frame_summaries") or [])[:12],
        "frame_paths": list(material.get("frame_paths") or [])[:12],
        "local_analysis": local_result,
    }
    return [
        {
            "role": "system",
            "content": (
                "你是电商爆款视频结构分析师。你只能基于可用证据分析：关键帧摘要、字幕/口播转写、用户补充画面摘要。"
                "禁止根据产品类目、标题或常识编造画面、人物、动作、字幕、功效和产品效果。"
            ),
        },
        {
            "role": "developer",
            "content": (
                "请只返回 JSON。字段必须包含：视频基础信息、口播/字幕转写、开头3秒钩子、视频节奏拆解、"
                "场景设计、人物关系、用户痛点、剧情冲突、产品出现时机、卖点植入方式、镜头/画面特点、"
                "字幕风格、情绪触发点、转化引导方式、可模仿结构、不能照搬的表达、适合迁移到哪些产品。"
                "每个关键结论尽量写依据，例如“依据：第1帧摘要 / 字幕口播 / 用户补充”。"
                "如果某项没有证据，必须输出“未识别到”。不得生成细节丰富但没有证据支持的剧情分析。"
            ),
        },
        {"role": "user", "content": json.dumps(compact_material, ensure_ascii=False)},
    ]


def _video_analysis_schema() -> Dict[str, Any]:
    fields = [
        "视频基础信息",
        "口播/字幕转写",
        "关键帧摘要",
        "可用证据",
        "分析可信度",
        "开头3秒钩子",
        "视频节奏拆解",
        "场景设计",
        "人物关系",
        "用户痛点",
        "剧情冲突",
        "产品出现时机",
        "卖点植入方式",
        "镜头/画面特点",
        "字幕风格",
        "情绪触发点",
        "转化引导方式",
        "可模仿结构",
        "不能照搬的表达",
        "适合迁移到哪些产品",
    ]
    return {
        "type": "object",
        "properties": {field: {"type": ["string", "array", "object"]} for field in fields},
        "required": fields,
        "additionalProperties": True,
    }


def _merge_video_analysis(local_result: Mapping[str, Any], payload: Mapping[str, Any]) -> Dict[str, Any]:
    result = dict(local_result)
    for field in _video_analysis_schema()["required"]:
        value = payload.get(field)
        if value:
            result[field] = value
    result["analysis_version"] = "v0.9-llm"
    return result


def _reject_unsupported_hallucinations(material: Mapping[str, Any], result: Mapping[str, Any]) -> None:
    evidence_text = _evidence_text(material) + "\n" + "\n".join(str(item) for item in material.get("frame_summaries") or [])
    result_text = json.dumps(result, ensure_ascii=False)
    unsupported_terms = ["婴儿", "宝妈", "宝宝", "护理台", "红屁屁", "洗脸台", "擦脸"]
    hallucinated = [term for term in unsupported_terms if term in result_text and term not in evidence_text]
    if hallucinated:
        raise ValueError(f"LLM analysis included unsupported details not present in evidence: {', '.join(hallucinated)}")


def _analysis_metadata(
    analysis_source: str,
    provider: str,
    model: str,
    fallback_reason: str = "",
    frame_extraction_error: str = "",
) -> Dict[str, str]:
    metadata = {
        "analysis_source": analysis_source,
        "provider": provider,
        "model": model,
    }
    if fallback_reason:
        metadata["fallback_reason"] = fallback_reason
    if frame_extraction_error:
        metadata["frame_extraction_error"] = frame_extraction_error
    return metadata


def _evidence_metadata(material: Mapping[str, Any]) -> Dict[str, Any]:
    evidence = _evidence_profile(material)
    return {
        "keyframe_count": evidence["可用证据"]["keyframe_count"],
        "extraction_backend": evidence["可用证据"]["extraction_backend"],
        "evidence_level": evidence["分析可信度"],
    }


def _evidence_text(material: Mapping[str, Any]) -> str:
    parts = [
        str(material.get("transcript") or material.get("manual_transcript") or ""),
        str(material.get("supplemental_copy") or material.get("manual_frame_summary") or ""),
    ]
    return "\n".join(part.strip() for part in parts if part.strip())


def _evidence_profile(material: Mapping[str, Any]) -> Dict[str, Any]:
    frame_paths = list(material.get("frame_paths") or [])
    frame_summaries = list(material.get("frame_summaries") or [])
    keyframe_count = int(material.get("keyframe_count") or len(frame_paths) or len(frame_summaries) or 0)
    transcript = str(material.get("transcript") or material.get("manual_transcript") or "").strip()
    supplemental = str(material.get("supplemental_copy") or material.get("manual_frame_summary") or "").strip()
    has_transcript = bool(transcript)
    has_supplemental = bool(supplemental)
    has_frame_summary = _has_visual_frame_summary(frame_summaries)
    if has_frame_summary and (has_transcript or has_supplemental):
        confidence = "高"
    elif has_frame_summary or has_transcript or has_supplemental:
        confidence = "中"
    elif keyframe_count > 0:
        confidence = "低"
    else:
        confidence = "不可分析"
    return {
        "可用证据": {
            "keyframe_count": keyframe_count,
            "transcript_exists": has_transcript,
            "supplemental_copy_exists": has_supplemental,
            "frame_summary_exists": has_frame_summary,
            "frame_paths": frame_paths[:12],
            "frame_timestamps": list(material.get("frame_timestamps") or [])[:12],
            "extraction_backend": material.get("frame_extraction_backend") or material.get("extraction_backend") or "",
            "attempted_backends": list(material.get("attempted_backends") or []),
        },
        "分析可信度": confidence,
    }


def _has_visual_frame_summary(frame_summaries: List[Any]) -> bool:
    for summary in frame_summaries:
        text = str(summary).strip()
        if text and "已抽取画面文件" not in text:
            return True
    return False


def _frame_extraction_error(material: Mapping[str, Any]) -> str:
    if int(material.get("keyframe_count") or len(material.get("frame_paths") or []) or 0) > 0:
        return ""
    attempted = list(material.get("attempted_backends") or [])
    error = str(material.get("frame_extraction_error") or material.get("frame_extraction_note") or "")
    if attempted and error:
        return f"{error}; attempted_backends={', '.join(str(item) for item in attempted)}"
    return error


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
    evidence_text = transcript + "\n" + "\n".join(str(item) for item in frame_summaries)
    candidates = ["户外", "街边", "路边", "浴室", "通勤前", "后厨", "工厂", "客厅", "办公室", "厨房", "门店", "梳妆台"]
    scenes = [item for item in candidates if item in evidence_text]
    if frame_summaries:
        scenes.extend(str(item) for item in frame_summaries if "已抽取画面文件" not in str(item))
    return scenes[:4] or ["未识别到"]


def _infer_persona(category: str, transcript: str) -> str:
    if "老板" in transcript and any(word in transcript for word in ["咋卖", "多少钱", "贵", "买", "卖"]):
        return "老板与顾客/路人"
    if "老板" in transcript:
        return "老板与对话对象"
    if "顾客" in transcript or "路人" in transcript:
        return "顾客与销售者"
    if "厨师" in transcript or "后厨" in transcript or "出餐" in transcript:
        return "餐饮老板与厨师"
    if "宝妈" in transcript or category == "母婴纸品类":
        return "宝妈与家庭成员" if "宝妈" in transcript or "宝宝" in transcript else "未识别到"
    if "闺蜜" in transcript:
        return "闺蜜与女主"
    return "未识别到"


def _infer_pain(category: str, transcript: str) -> str:
    if any(word in transcript for word in ["贵", "咋卖", "10块", "十块", "多少钱", "别买"]):
        return "价格异议和产品价值感需要通过真人对话解释"
    if "扁塌" in transcript or "头发" in transcript:
        return "用户担心状态不好、使用体验不够直观"
    if "出餐" in transcript or "后厨" in transcript:
        return "高峰期效率和稳定出品压力"
    return "未识别到"


def _infer_conflict(category: str, transcript: str) -> str:
    if any(word in transcript for word in ["嫌贵", "贵", "别买", "学一个"]):
        return "围绕价格贵不贵展开对话冲突，靠真人互动制造停留"
    if "没想到" in transcript or "但是" in transcript:
        return "预期和实际体验之间形成反差"
    return "未识别到"


def _infer_product_timing(transcript: str) -> str:
    if any(word in transcript for word in ["纸巾", "产品", "这包", "这纸"]):
        return "产品在对话开头或中段随手持展示出现"
    if "先别急" in transcript:
        return "先抛出问题，再让产品在解决方案阶段出现"
    return "未识别到"


def _infer_placement(transcript: str) -> str:
    if any(word in transcript for word in ["手持", "纸巾", "咋卖", "一包"]):
        return "通过真人手持产品和价格对话自然露出产品"
    if "测评" in transcript or "实测" in transcript:
        return "通过演示和对比完成卖点证明"
    return "未识别到"


def _infer_visual_features(transcript: str, frame_summaries: List[str], rules: Mapping[str, Any]) -> List[str]:
    keywords = rules.get("visual_keywords") or []
    found = [item for item in keywords if item in transcript]
    if any(word in transcript for word in ["户外", "手持", "纸巾", "老板", "咋卖"]):
        found.extend([word for word in ["户外真人", "手持产品", "对话字幕", "产品近景"] if word not in found])
    if frame_summaries:
        found.extend(str(item) for item in frame_summaries if "已抽取画面文件" not in str(item))
    return found[:5] or ["未识别到"]


def _infer_subtitle_style(transcript: str) -> str:
    if any(word in transcript for word in ["咋卖", "嫌贵", "学一个"]):
        return "对话式短字幕，突出价格冲突和真人反应"
    if len(transcript) > 120:
        return "短句分行、重点词前置，适合短视频快节奏阅读"
    return "未识别到"


def _infer_emotions(category: str) -> List[str]:
    return ["需依据口播/字幕或画面摘要进一步判断"]


def _infer_conversion(transcript: str, rules: Mapping[str, Any]) -> str:
    for keyword in rules.get("conversion_keywords", []):
        if keyword in transcript:
            return "用收藏、评论、咨询或查看链接承接兴趣"
    return "未识别到"


def _avoid_expressions(sentences: List[str]) -> List[str]:
    return [sentence[:42] for sentence in sentences if len(sentence) >= 10][:5] or ["原视频完整句子、品牌名、人名和专属剧情细节不能照搬"]


def _suitable_products(category: str) -> List[str]:
    return [f"{category}同类产品", "同一对话冲突结构可迁移的电商产品"]
