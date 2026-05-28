"""Generate original scripts by imitating video structure, not wording."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .category import recognize_category
from .compliance import check_compliance
from .config import PROJECT_ROOT, load_yaml_like
from .llm import LLMClient, resolve_llm_client
from .models import ProductInfo
from .script_modes import normalize_script_options


RULE_PATH = PROJECT_ROOT / "rules" / "video_imitation_rules.json"


def generate_video_imitation_scripts(
    product_info: ProductInfo,
    video_analysis: Mapping[str, Any],
    video_material: Mapping[str, Any],
    version_count: int = 3,
    settings: Optional[Dict[str, Any]] = None,
    llm_client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    product, normalization_metadata = normalize_script_options(product_info.normalized())
    rules = _load_rules()
    allowed_counts = rules.get("version_counts") or [3, 5, 8]
    version_count = int(version_count or 3)
    if version_count not in allowed_counts:
        version_count = 3

    category = recognize_category(product.product_name, product.selling_points, product.category)
    original_text = str(video_material.get("transcript") or video_material.get("manual_transcript") or "")
    variants = []
    for index in range(version_count):
        variant = _build_video_variant(product, category, video_analysis, index)
        variant["similarity_avoidance"] = _check_similarity(variant["full_text"], original_text)
        variant["compliance"] = [risk.__dict__ for risk in check_compliance(variant["full_text"])]
        variant["quality_score"] = _score_variant(product, variant)
        variants.append(variant)

    combined = "\n\n".join(item["full_text"] for item in variants)
    risks = check_compliance(combined)
    output = {
        "video_analysis_report": dict(video_analysis),
        "original_scripts": variants,
        "risk_terms": [risk.__dict__ for risk in risks],
        "similarity_avoidance": _similarity_summary(variants),
        "metadata": {
            "generation_source": "video_structure_imitation",
            "analysis_source": _video_analysis_source(video_analysis),
            "provider": "local",
            "model": "local",
            "generation_mode": product.generation_mode,
            "requested_generation_mode": product.generation_mode,
            "script_mode": product.script_mode,
            "category": category,
            "video_title": video_material.get("title", ""),
            "source_url": video_material.get("source_url", ""),
            "normalized_script_subtype": normalization_metadata.get("normalized_script_subtype", product.script_subtype),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
    }
    output = _maybe_apply_llm_video_imitation(product, video_analysis, video_material, output, settings, llm_client)
    output["markdown"] = render_video_imitation_markdown(product, output)
    return output


def _maybe_apply_llm_video_imitation(
    product: ProductInfo,
    video_analysis: Mapping[str, Any],
    video_material: Mapping[str, Any],
    local_output: Dict[str, Any],
    settings: Optional[Dict[str, Any]],
    llm_client: Optional[LLMClient],
) -> Dict[str, Any]:
    if settings is None and llm_client is None:
        return local_output

    client, resolve_error = resolve_llm_client(settings=settings, llm_client=llm_client)
    if client is None:
        local_output["metadata"].update(
            {
                "generation_source": "local_fallback",
                "provider": "local",
                "model": "local",
                "generation_mode": "local_only",
                "fallback_reason": resolve_error or "LLM provider is local",
            }
        )
        return local_output

    provider = getattr(client, "provider_name", "unknown")
    model = getattr(client, "model", "unknown")
    try:
        payload = client.generate(
            _video_imitation_messages(product, video_analysis, video_material, local_output),
            _video_imitation_schema(),
        )
        variants = _normalize_llm_video_variants(product, payload.get("original_scripts"), video_material)
        if len(variants) < 3:
            raise ValueError("LLM video imitation returned fewer than 3 script versions")
        combined = "\n\n".join(item["full_text"] for item in variants)
        risks = check_compliance(combined)
        output = dict(local_output)
        output["original_scripts"] = variants
        output["risk_terms"] = [risk.__dict__ for risk in risks]
        output["similarity_avoidance"] = _similarity_summary(variants)
        output["metadata"] = {
            **dict(local_output.get("metadata", {})),
            "generation_source": "llm_video_imitation",
            "provider": provider,
            "model": model,
        }
        output["metadata"].pop("fallback_reason", None)
        return output
    except Exception as exc:
        local_output["metadata"].update(
            {
                "generation_source": "local_fallback",
                "provider": provider,
                "model": model,
                "generation_mode": "local_only",
                "fallback_reason": str(exc),
            }
        )
        return local_output


def _video_imitation_messages(
    product: ProductInfo,
    video_analysis: Mapping[str, Any],
    video_material: Mapping[str, Any],
    local_output: Mapping[str, Any],
) -> List[Dict[str, str]]:
    request = {
        "target_product": product.__dict__,
        "video_analysis": video_analysis,
        "video_source": {
            "title": video_material.get("title", ""),
            "platform": video_material.get("platform", ""),
            "source_url": video_material.get("source_url", ""),
            "transcript_excerpt": str(video_material.get("transcript") or video_material.get("manual_transcript") or "")[:2000],
        },
        "required_count": len(local_output.get("original_scripts", [])),
    }
    return [
        {
            "role": "system",
            "content": (
                "你是电商视频爆款原创仿写编导。你可以模仿视频结构、节奏、钩子和转化逻辑，"
                "但必须为目标产品生成原创脚本。"
            ),
        },
        {
            "role": "developer",
            "content": (
                "只返回 JSON，必须包含 original_scripts 数组。不得照抄原视频文案，不得保留原视频品牌名、人名、专属剧情细节。"
                "真人实拍模式不得输出 AI画面提示词、负面提示词、连续性要求、可直接复制版提示词。"
                "AI视频模式必须输出 AI画面提示词、镜头运动、负面提示词、连续性要求、可直接复制版提示词。"
            ),
        },
        {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
    ]


def _video_imitation_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "original_scripts": {
                "type": "array",
                "items": {"type": "object"},
            }
        },
        "required": ["original_scripts"],
        "additionalProperties": True,
    }


def _normalize_llm_video_variants(
    product: ProductInfo,
    variants: Any,
    video_material: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    if not isinstance(variants, list):
        return []
    original_text = str(video_material.get("transcript") or video_material.get("manual_transcript") or "")
    normalized = []
    for index, raw in enumerate(variants[:8]):
        if not isinstance(raw, Mapping):
            continue
        item = {
            "方案名称": str(raw.get("方案名称") or f"LLM原创仿写方案 {index + 1}"),
            "参考了视频的什么结构": raw.get("参考了视频的什么结构", ""),
            "原创改动点": raw.get("原创改动点", ["替换为当前产品", "重写场景和台词", "调整转化引导"]),
            "适合平台": raw.get("适合平台", product.platform),
            "开头钩子": raw.get("开头钩子", ""),
            "完整脚本": raw.get("完整脚本", ""),
            "字幕文案": raw.get("字幕文案", []),
            "口播/对白": raw.get("口播/对白") or raw.get("对白/口播") or "",
            "分镜/画面建议": raw.get("分镜/画面建议", []),
            "产品植入方式": raw.get("产品植入方式", ""),
            "结尾转化引导": raw.get("结尾转化引导", ""),
        }
        if product.script_mode == "ai_video":
            item.update(
                {
                    "AI画面提示词": raw.get("AI画面提示词", ""),
                    "镜头运动": raw.get("镜头运动", ""),
                    "负面提示词": raw.get("负面提示词", "照抄原视频, 原品牌名, 原人名, 夸大承诺, 医疗功效, 低清画面, 字幕错乱"),
                    "连续性要求": raw.get("连续性要求", "人物、产品、场景和字幕风格保持连续。"),
                    "可直接复制版提示词": raw.get("可直接复制版提示词", ""),
                }
            )
        full_text = json.dumps(item, ensure_ascii=False)
        item["full_text"] = full_text
        item["similarity_avoidance"] = _check_similarity(full_text, original_text)
        item["compliance"] = [risk.__dict__ for risk in check_compliance(full_text)]
        item["quality_score"] = _score_variant(product, item)
        normalized.append(item)
    return normalized


def _video_analysis_source(video_analysis: Mapping[str, Any]) -> str:
    metadata = video_analysis.get("metadata") if isinstance(video_analysis.get("metadata"), dict) else {}
    return str(metadata.get("analysis_source") or "unknown")


def render_video_imitation_markdown(product: ProductInfo, output: Mapping[str, Any]) -> str:
    lines = [
        f"# {product.product_name} 视频爆款原创仿写脚本",
        "",
        "## 视频爆款解析",
        "",
    ]
    analysis = output.get("video_analysis_report") or {}
    for field in [
        "视频基础信息",
        "口播/字幕转写",
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
    ]:
        lines.append(f"- {field}：{_format_value(analysis.get(field, '未提取'))}")

    for variant in output.get("original_scripts", []):
        lines.extend(["", f"## {variant.get('方案名称')}", ""])
        for field in [
            "参考了视频的什么结构",
            "原创改动点",
            "适合平台",
            "开头钩子",
            "完整脚本",
            "字幕文案",
            "口播/对白",
            "分镜/画面建议",
            "产品植入方式",
            "结尾转化引导",
        ]:
            lines.append(f"- {field}：{_format_value(variant.get(field, ''))}")
        if product.script_mode == "ai_video":
            for field in ["AI画面提示词", "镜头运动", "负面提示词", "连续性要求", "可直接复制版提示词"]:
                lines.append(f"- {field}：{_format_value(variant.get(field, ''))}")
        lines.append(f"- 合规检查：{_format_value(variant.get('compliance') or '未命中内置高风险词')}")
        lines.append(f"- 相似度规避说明：{variant.get('similarity_avoidance', {}).get('note', '')}")
        lines.append(f"- 质量评分：{variant.get('quality_score', 0)}/100")

    lines.extend(["", "## 合规检查", ""])
    risks = output.get("risk_terms") or []
    if risks:
        for risk in risks:
            lines.append(f"- 高风险词：{risk.get('term')}｜替代表达：{risk.get('replacement')}")
    else:
        lines.append("- 未命中内置高风险词。")

    lines.extend(["", "## 相似度规避说明", "", str(output.get("similarity_avoidance", ""))])
    lines.extend(["", "## metadata", "", "```json", json.dumps(output.get("metadata", {}), ensure_ascii=False, indent=2), "```"])
    return "\n".join(lines).strip() + "\n"


def write_video_imitation_outputs(product: ProductInfo, output: Mapping[str, Any], output_dir: Optional[Path] = None) -> Tuple[Path, Path]:
    active_output_dir = output_dir or PROJECT_ROOT / "outputs"
    active_output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", product.product_name).strip("_") or "product"
    markdown_path = active_output_dir / f"{timestamp}_{safe_name}_video_imitation.md"
    json_path = active_output_dir / f"{timestamp}_{safe_name}_video_imitation.json"
    markdown_path.write_text(str(output.get("markdown", "")), encoding="utf-8")
    json_payload = {key: value for key, value in output.items() if key != "markdown"}
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return markdown_path, json_path


def _build_video_variant(product: ProductInfo, category: str, analysis: Mapping[str, Any], index: int) -> Dict[str, Any]:
    structure = str(analysis.get("可模仿结构") or analysis.get("视频节奏拆解") or "钩子 -> 冲突 -> 产品 -> 证明 -> 转化")
    scenes = _scene_options(category)
    personas = _persona_options(category)
    scene = scenes[index % len(scenes)]
    persona = personas[index % len(personas)]
    hook = _hook(product, scene, index)
    conflict = _conflict(product, category, scene)
    placement = _placement(product, index)
    conversion = _conversion(product, index)
    subtitles = [hook, "把问题放进真实场景", product.product_name, "看得见的使用理由", "先收藏，对照需求选择"]
    voiceover = f"{hook}\n{conflict}\n这次换成{product.product_name}，重点看{product.selling_points}。\n{conversion}"
    storyboard = [
        f"开场：{scene}里{persona}抛出问题",
        f"中段：产品在解决动作中出现，展示{product.selling_points}",
        "结尾：产品定格，给出低门槛行动引导",
    ]
    base = {
        "方案名称": f"原创仿写方案 {index + 1}",
        "参考了视频的什么结构": structure,
        "原创改动点": ["替换为当前产品", f"场景改为{scene}", f"人物关系改为{persona}", "重写台词表达"],
        "适合平台": product.platform,
        "开头钩子": hook,
        "完整脚本": voiceover,
        "字幕文案": subtitles,
        "口播/对白": voiceover,
        "分镜/画面建议": storyboard,
        "产品植入方式": placement,
        "结尾转化引导": conversion,
    }
    if product.script_mode == "ai_video":
        base.update(
            {
                "AI画面提示词": f"{scene}，{persona}，电商短剧质感，产品{product.product_name}自然露出，画面清晰，字幕简洁",
                "镜头运动": "开头快速推近，中段跟拍产品动作，结尾慢推产品定格",
                "负面提示词": "照抄原视频, 原品牌名, 原人名, 夸大承诺, 医疗功效, 低清画面, 字幕错乱",
                "连续性要求": "人物服装、产品包装、场景光线保持一致，产品露出从中段到结尾连续。",
                "可直接复制版提示词": f"为{product.product_name}生成9:16电商短剧广告，结构参考钩子-冲突-产品-证明-转化，场景为{scene}，人物关系为{persona}，卖点是{product.selling_points}，避免照抄原视频。",
            }
        )
    base["full_text"] = json.dumps(base, ensure_ascii=False)
    return base


def _scene_options(category: str) -> List[str]:
    if category == "冻品餐饮类":
        return ["后厨高峰期", "备菜台", "出餐窗口"]
    if category == "1688工厂定制类":
        return ["工厂样品间", "打样沟通现场", "仓库发货区"]
    if category == "母婴纸品类":
        return ["客厅亲子区", "婴儿护理台", "外出包整理场景"]
    return ["通勤前梳妆台", "浴室洗护场景", "办公室状态反差场景"]


def _persona_options(category: str) -> List[str]:
    if category == "冻品餐饮类":
        return ["餐饮老板与厨师", "厨师与服务员", "老板与采购"]
    if category == "1688工厂定制类":
        return ["工厂老板与客户", "业务员与采购", "老板探厂"]
    if category == "母婴纸品类":
        return ["宝妈与宝宝", "宝妈与家人", "宝妈与闺蜜"]
    return ["闺蜜与女主", "职场同事", "种草博主与用户"]


def _hook(product: ProductInfo, scene: str, index: int) -> str:
    hooks = [
        f"别急着照搬爆款，先看{product.product_name}在{scene}里怎么解决真实问题。",
        f"同样的爆款节奏，换成{product.product_name}要先改这个开头。",
        f"如果你是{product.audience}，这个场景比一句口号更有说服力。",
    ]
    return hooks[index % len(hooks)]


def _conflict(product: ProductInfo, category: str, scene: str) -> str:
    return f"{scene}里先放大{category}用户的真实顾虑，再让产品用可见动作承接。"


def _placement(product: ProductInfo, index: int) -> str:
    placements = [
        f"先出现人物困扰，再让{product.product_name}在解决动作中自然入镜。",
        f"用产品特写承接{product.selling_points}，避免硬广式口播。",
        f"把{product.product_name}放在情绪反转的关键镜头里。",
    ]
    return placements[index % len(placements)]


def _conversion(product: ProductInfo, index: int) -> str:
    endings = [
        "先收藏，对照自己的需求再选择。",
        "想看同类场景，可以先记下这个产品逻辑。",
        "按自己的使用频率和规格需求理性选择。",
    ]
    return endings[index % len(endings)]


def _check_similarity(text: str, original_text: str) -> Dict[str, Any]:
    reused = [sentence for sentence in _split_sentences(original_text) if len(sentence) >= 10 and sentence in text]
    return {
        "is_too_similar": bool(reused),
        "reused_sentences": reused[:5],
        "note": "未复用原视频完整句子。" if not reused else "发现原视频完整句子复用，请重新改写。",
    }


def _similarity_summary(variants: List[Mapping[str, Any]]) -> str:
    if any(item.get("similarity_avoidance", {}).get("is_too_similar") for item in variants):
        return "部分方案与原视频文案过近，建议重新生成或手动改写。"
    return "已按视频结构、节奏和转化逻辑迁移，未复用原视频完整句子、品牌名、人名或专属剧情细节。"


def _score_variant(product: ProductInfo, variant: Mapping[str, Any]) -> int:
    score = 82
    if product.script_mode == "ai_video" and variant.get("AI画面提示词") and variant.get("负面提示词"):
        score += 8
    if product.script_mode == "live_action" and "AI画面提示词" not in variant:
        score += 8
    if variant.get("similarity_avoidance", {}).get("is_too_similar"):
        score -= 20
    if variant.get("compliance"):
        score -= min(12, len(variant.get("compliance", [])) * 4)
    return max(0, min(100, score))


def _load_rules() -> Dict[str, Any]:
    return load_yaml_like(RULE_PATH) if RULE_PATH.exists() else {}


def _split_sentences(text: str) -> List[str]:
    chunks = re.split(r"[\n。！？!?；;]+", text)
    return [chunk.strip(" ，,：:") for chunk in chunks if chunk.strip()]


def _format_value(value: Any) -> str:
    if isinstance(value, dict):
        return "；".join(f"{key}：{val}" for key, val in value.items())
    if isinstance(value, list):
        return "；".join(str(item) for item in value)
    return str(value)
