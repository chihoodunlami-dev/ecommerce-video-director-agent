"""Create original scripts by transferring structures from reference materials."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .category import get_strategy, recognize_category
from .compliance import check_compliance
from .config import PROJECT_ROOT, load_yaml_like
from .llm import LLMClient, resolve_llm_client
from .models import ProductInfo
from .script_modes import normalize_script_options


REWRITE_RULE_PATH = PROJECT_ROOT / "rules" / "rewrite_rules.json"
SIMILARITY_RULE_PATH = PROJECT_ROOT / "rules" / "similarity_avoidance_rules.json"


def generate_original_scripts_from_references(
    product_info: ProductInfo,
    references: List[Mapping[str, Any]],
    version_count: int = 3,
    settings: Optional[Dict[str, Any]] = None,
    llm_client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    product, normalization_metadata = normalize_script_options(product_info.normalized())
    rewrite_rules = _load_rules(REWRITE_RULE_PATH)
    similarity_rules = _load_rules(SIMILARITY_RULE_PATH)
    min_count = int(rewrite_rules.get("version_count", {}).get("min", 3))
    max_count = int(rewrite_rules.get("version_count", {}).get("max", 5))
    version_count = max(min_count, min(max_count, int(version_count or min_count)))

    category = recognize_category(product.product_name, product.selling_points, product.category)
    strategy = get_strategy(category).__dict__
    references = list(references)[:5]
    formulas = _extract_formulas(references)
    variants = []
    for index in range(version_count):
        variant = _build_variant(product, category, strategy, references, rewrite_rules, index)
        variant["similarity_check"] = _check_similarity(variant["markdown"], references, similarity_rules)
        variant["risk_terms"] = [risk.__dict__ for risk in check_compliance(variant["markdown"])]
        variants.append(variant)

    combined_text = "\n\n".join(item["markdown"] for item in variants)
    risks = check_compliance(combined_text)
    quality_score = _score_rewrite_output(product, variants, references, risks)
    output = {
        "reference_analysis_report": _reference_report(references),
        "boom_formula": formulas,
        "original_scripts": variants,
        "risk_terms": [risk.__dict__ for risk in risks],
        "similarity_avoidance": _similarity_summary(variants, references),
        "quality_score": quality_score,
        "metadata": {
            "generation_source": "reference_structure_transfer",
            "analysis_source": _reference_analysis_source(references),
            "provider": "local",
            "model": "local",
            "generation_mode": product.generation_mode,
            "requested_generation_mode": product.generation_mode,
            "script_mode": product.script_mode,
            "category": category,
            "reference_ids": [item.get("id", "") for item in references],
            "reference_links": [item.get("source_url", "") for item in references if item.get("source_url")],
            "normalized_script_subtype": normalization_metadata.get("normalized_script_subtype", product.script_subtype),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
    }
    output = _maybe_apply_llm_reference_rewrite(product, references, output, settings, llm_client)
    output["markdown"] = render_reference_rewrite_markdown(product, output)
    return output


def _maybe_apply_llm_reference_rewrite(
    product: ProductInfo,
    references: List[Mapping[str, Any]],
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
        payload = client.generate(_reference_rewrite_messages(product, references, local_output), _reference_rewrite_schema())
        variants = _normalize_llm_reference_variants(product, payload.get("original_scripts"), references)
        if len(variants) < 3:
            raise ValueError("LLM rewrite returned fewer than 3 script versions")

        combined_text = "\n\n".join(item["markdown"] for item in variants)
        risks = check_compliance(combined_text)
        output = dict(local_output)
        output["original_scripts"] = variants
        output["risk_terms"] = [risk.__dict__ for risk in risks]
        output["similarity_avoidance"] = _similarity_summary(variants, references)
        output["quality_score"] = _score_rewrite_output(product, variants, references, risks)
        output["metadata"] = {
            **dict(local_output.get("metadata", {})),
            "generation_source": "llm_reference_rewrite",
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


def _reference_rewrite_messages(
    product: ProductInfo,
    references: List[Mapping[str, Any]],
    local_output: Mapping[str, Any],
) -> List[Dict[str, str]]:
    compact_references = []
    for item in references[:5]:
        analysis = item.get("analysis_result") if isinstance(item.get("analysis_result"), dict) else {}
        compact_references.append(
            {
                "title": item.get("title", ""),
                "platform": item.get("platform", ""),
                "source_url": item.get("source_url", ""),
                "category": item.get("category", ""),
                "content_type": item.get("content_type", ""),
                "analysis_result": analysis,
                "avoid": analysis.get("不能照搬的表达", []),
            }
        )
    request = {
        "target_product": product.__dict__,
        "references": compact_references,
        "local_structure_example": {
            "boom_formula": local_output.get("boom_formula", []),
            "script_mode": product.script_mode,
            "required_count": len(local_output.get("original_scripts", [])),
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "你是电商短视频原创迁移编导。你的任务是学习参考素材的结构和思路，"
                "为目标产品写全新原创脚本，禁止照抄原文或只替换产品名。"
            ),
        },
        {
            "role": "developer",
            "content": (
                "只返回 JSON。必须生成 original_scripts 数组。每个方案至少在开头钩子、场景、人物关系、"
                "剧情冲突、产品植入方式、转化引导或表达风格中三项不同。"
                "真人实拍模式禁止出现 AI画面提示词、负面提示词、连续性要求；AI视频模式必须包含这些字段。"
                "不要复用参考素材完整句子、品牌名、人名或专属剧情细节。"
            ),
        },
        {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
    ]


def _reference_rewrite_schema() -> Dict[str, Any]:
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


def _normalize_llm_reference_variants(
    product: ProductInfo,
    variants: Any,
    references: List[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    if not isinstance(variants, list):
        return []
    normalized = []
    for index, raw in enumerate(variants[:5]):
        if not isinstance(raw, Mapping):
            continue
        sections = raw.get("sections") if isinstance(raw.get("sections"), list) else []
        markdown = str(raw.get("markdown") or "")
        if not markdown:
            markdown = _variant_markdown(product, sections, script_mode=product.script_mode) if sections else _llm_variant_markdown(product, raw)
        if product.script_mode == "live_action":
            markdown = _strip_ai_only_fields(markdown)
        item = {
            "version": int(raw.get("version") or index + 1),
            "title": str(raw.get("title") or raw.get("方案标题") or f"LLM原创方案 {index + 1}"),
            "hook": str(raw.get("hook") or raw.get("开头钩子") or ""),
            "scene": str(raw.get("scene") or raw.get("场景") or ""),
            "persona_relation": str(raw.get("persona_relation") or raw.get("人物关系") or ""),
            "content_structure": str(raw.get("content_structure") or raw.get("内容结构") or ""),
            "plot_conflict": str(raw.get("plot_conflict") or raw.get("剧情冲突") or ""),
            "product_placement": str(raw.get("product_placement") or raw.get("产品植入方式") or ""),
            "conversion": str(raw.get("conversion") or raw.get("转化引导") or ""),
            "variation_axes": raw.get("variation_axes") if isinstance(raw.get("variation_axes"), list) else ["开头钩子", "场景", "产品植入方式"],
            "sections": sections,
            "markdown": markdown,
        }
        item["similarity_check"] = _check_similarity(item["markdown"], references, _load_rules(SIMILARITY_RULE_PATH))
        item["risk_terms"] = [risk.__dict__ for risk in check_compliance(item["markdown"])]
        normalized.append(item)
    return normalized


def _llm_variant_markdown(product: ProductInfo, raw: Mapping[str, Any]) -> str:
    if product.script_mode == "live_action":
        fields = ["开头钩子", "完整脚本", "字幕文案", "口播/对白", "分镜/画面建议", "产品植入方式", "结尾转化引导"]
    else:
        fields = ["开头钩子", "完整脚本", "AI画面提示词", "镜头运动", "字幕文案", "对白/口播", "负面提示词", "连续性要求", "可直接复制版提示词"]
    lines = []
    for field in fields:
        value = raw.get(field) or raw.get(field.lower())
        if value:
            lines.append(f"- {field}：{_format_value(value)}")
    return "\n".join(lines) or str(raw)


def _strip_ai_only_fields(text: str) -> str:
    blocked = ["AI画面提示词", "负面提示词", "连续性要求", "可直接复制版提示词"]
    return "\n".join(line for line in text.splitlines() if not any(field in line for field in blocked))


def _reference_analysis_source(references: List[Mapping[str, Any]]) -> str:
    sources = []
    for item in references:
        analysis = item.get("analysis_result") if isinstance(item.get("analysis_result"), dict) else {}
        metadata = analysis.get("metadata") if isinstance(analysis.get("metadata"), dict) else {}
        if metadata.get("analysis_source"):
            sources.append(str(metadata["analysis_source"]))
    return ",".join(sorted(set(sources))) if sources else "unknown"


def render_reference_rewrite_markdown(product: ProductInfo, output: Mapping[str, Any]) -> str:
    lines = [
        f"# {product.product_name} 爆款素材原创迁移脚本",
        "",
        "## 参考素材分析报告",
        "",
    ]
    report = output.get("reference_analysis_report") or []
    for index, item in enumerate(report, start=1):
        lines.extend(
            [
                f"### 素材 {index}：{item.get('title', '未命名素材')}",
                f"- 平台：{item.get('platform', '未填写')}",
                f"- 链接：{item.get('source_url', '未填写')}",
            ]
        )
        analysis = item.get("analysis_result") or {}
        for field in [
            "开头钩子",
            "用户痛点",
            "目标人群",
            "场景设计",
            "人物关系",
            "内容结构",
            "卖点植入方式",
            "情绪触发点",
            "转化引导方式",
            "可复用思路",
            "不能照搬的表达",
            "适合迁移的产品类型",
        ]:
            value = analysis.get(field, "未提取")
            lines.append(f"- {field}：{_format_value(value)}")
        lines.append("")

    lines.extend(["## 提取到的爆款公式", ""])
    for formula in output.get("boom_formula", []):
        lines.append(f"- {formula}")

    for variant in output.get("original_scripts", []):
        lines.extend(["", f"## 原创脚本方案 {variant.get('version')}", ""])
        lines.append(f"- 方案标题：{variant.get('title')}")
        lines.append(f"- 差异化方向：{_format_value(variant.get('variation_axes', []))}")
        lines.append("")
        lines.append(variant.get("markdown", ""))

    lines.extend(["", "## 合规检查", ""])
    risks = output.get("risk_terms") or []
    if risks:
        for risk in risks:
            lines.append(f"- 高风险词：{risk.get('term')}｜替代表达：{risk.get('replacement')}")
    else:
        lines.append("- 未命中内置高风险词。")

    lines.extend(["", "## 相似度规避说明", ""])
    lines.append(str(output.get("similarity_avoidance", "")))

    quality = output.get("quality_score") or {}
    lines.extend(["", "## 质量评分", "", f"- 总分：{quality.get('score', 0)}/100"])
    for item in quality.get("suggestions", []):
        lines.append(f"- {item}")

    lines.extend(["", "## metadata", "", "```json", json.dumps(output.get("metadata", {}), ensure_ascii=False, indent=2), "```"])
    return "\n".join(lines).strip() + "\n"


def write_reference_rewrite_outputs(
    product: ProductInfo,
    output: Mapping[str, Any],
    output_dir: Optional[Path] = None,
) -> Tuple[Path, Path]:
    active_output_dir = output_dir or PROJECT_ROOT / "outputs"
    active_output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", product.product_name).strip("_") or "product"
    markdown_path = active_output_dir / f"{timestamp}_{safe_name}_reference_rewrite.md"
    json_path = active_output_dir / f"{timestamp}_{safe_name}_reference_rewrite.json"
    markdown_path.write_text(str(output.get("markdown", "")), encoding="utf-8")
    json_payload = {key: value for key, value in output.items() if key != "markdown"}
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return markdown_path, json_path


def _build_variant(
    product: ProductInfo,
    category: str,
    strategy: Mapping[str, Any],
    references: List[Mapping[str, Any]],
    rules: Mapping[str, Any],
    index: int,
) -> Dict[str, Any]:
    category_angles = (rules.get("category_rewrite_angles") or {}).get(category) or strategy.get("scenes") or ["真实使用场景"]
    personas = _reference_values(references, "人物关系") or strategy.get("recommended_personas") or ["用户与种草者"]
    structures = _reference_values(references, "内容结构") or ["痛点开场 -> 产品出现 -> 细节证明 -> 转化引导"]
    conversions = _reference_values(references, "转化引导方式") or ["收藏后对照需求选择"]

    angle = str(category_angles[index % len(category_angles)])
    persona = str(personas[index % len(personas)])
    structure = str(structures[index % len(structures)])
    conversion = str(conversions[index % len(conversions)])
    hook = _original_hook(product, category, angle, index)
    conflict = _category_conflict(category, product, angle)
    placement = _product_placement(product, category, index)
    axes = ["开头钩子", "场景", "人物关系", "剧情冲突", "产品植入方式", "转化引导", "表达风格"]

    if product.script_mode == "live_action":
        scenes = _build_live_action_sections(product, hook, conflict, placement, conversion, angle, persona)
    else:
        scenes = _build_ai_video_sections(product, hook, conflict, placement, conversion, angle, persona)

    markdown = _variant_markdown(product, scenes, script_mode=product.script_mode)
    return {
        "version": index + 1,
        "title": f"{angle}原创方案",
        "hook": hook,
        "scene": angle,
        "persona_relation": persona,
        "content_structure": structure,
        "plot_conflict": conflict,
        "product_placement": placement,
        "conversion": conversion,
        "variation_axes": axes[index : index + 3] if index + 3 <= len(axes) else axes[-3:],
        "sections": scenes,
        "markdown": markdown,
    }


def _build_live_action_sections(product, hook, conflict, placement, conversion, angle, persona) -> List[Dict[str, str]]:
    return [
        {"标题": "开头3秒钩子", "口播内容": hook, "画面建议": f"{angle}里直接出现真实人物状态", "字幕文案": hook, "镜头建议": "近景切中景"},
        {"标题": "痛点引入", "口播内容": conflict, "画面建议": f"{persona}围绕真实困扰自然交流", "字幕文案": "真实问题先说清楚", "镜头建议": "手持跟拍"},
        {"标题": "产品介绍", "口播内容": f"这次换成{product.product_name}，重点看它是否适合{product.audience}。", "画面建议": "产品正面入镜，包装信息清晰", "字幕文案": product.product_name, "镜头建议": "产品特写"},
        {"标题": "卖点展开", "口播内容": f"把卖点拆开看：{product.selling_points}。", "画面建议": placement, "字幕文案": "卖点看得见，表达不夸张", "镜头建议": "细节特写"},
        {"标题": "使用场景", "口播内容": f"放到{angle}里，它的价值会比单纯口播更直观。", "画面建议": "真实使用动作连续呈现", "字幕文案": "回到真实使用场景", "镜头建议": "中景稳定镜头"},
        {"标题": "价格/机制", "口播内容": product.price_mechanism or "按自己的使用频率和规格需求选择。", "画面建议": "规格、组合和购买机制简洁展示", "字幕文案": "先看清规格和需求", "镜头建议": "平移展示"},
        {"标题": "结尾引导", "口播内容": conversion, "画面建议": "人物自然拿起产品并收束", "字幕文案": "先收藏，再对照需求选择", "镜头建议": "定格产品"},
    ]


def _build_ai_video_sections(product, hook, conflict, placement, conversion, angle, persona) -> List[Dict[str, str]]:
    negative = "照抄参考文案, 夸大承诺, 医疗功效, 绝对化表达, 低清画面, 字幕错乱"
    return [
        {"标题": "0-3秒 冲击力开篇", "AI画面提示词": f"{angle}，{persona}，人物表情带有轻微紧张，产品未急于出现，电商短剧质感", "镜头运动": "快速推近到人物表情", "人物动作": "人物看向镜头抛出问题", "产品露出方式": "产品虚化在桌面边缘", "字幕文案": hook, "对白/口播": hook, "负面提示词": negative},
        {"标题": "4-15秒 冲突铺垫", "AI画面提示词": f"{angle}里的真实困扰被放大，环境细节清晰，符合{product.audience}日常", "镜头运动": "跟拍转特写", "人物动作": "人物展示困扰并与对方交流", "产品露出方式": "产品仍作为待解决方案出现", "字幕文案": "问题越具体，需求越明确", "对白/口播": conflict, "负面提示词": negative},
        {"标题": "16-25秒 产品植入", "AI画面提示词": f"{product.product_name}清晰入镜，包装可读，围绕{product.selling_points}做细节展示", "镜头运动": "产品特写到使用动作", "人物动作": "人物拿起产品进行演示", "产品露出方式": placement, "字幕文案": product.product_name, "对白/口播": f"这一步不夸张，重点看{product.selling_points}这些真实细节。", "负面提示词": negative},
        {"标题": "26-35秒 情绪反转", "AI画面提示词": f"人物从犹豫变成认可，场景保持{angle}，画面明亮但真实", "镜头运动": "中景环绕到产品定格", "人物动作": "人物点头并回到使用场景", "产品露出方式": "产品与使用结果同框", "字幕文案": "场景里看到价值", "对白/口播": f"适合{product.audience}的原因，是它能回到具体使用场景里。", "负面提示词": negative},
        {"标题": "36秒后 成交引导", "AI画面提示词": "电商短剧结尾，产品居中，人物自然递出产品，字幕简洁", "镜头运动": "慢推产品定格", "人物动作": "人物做出收藏或查看动作", "产品露出方式": "产品正面和关键信息清晰露出", "字幕文案": "先收藏，对照需求选择", "对白/口播": conversion, "负面提示词": negative},
    ]


def _variant_markdown(product: ProductInfo, sections: List[Mapping[str, str]], script_mode: str) -> str:
    lines = []
    for section in sections:
        lines.extend([f"### {section.get('标题')}", ""])
        if script_mode == "live_action":
            for field in ["口播内容", "画面建议", "字幕文案", "镜头建议"]:
                lines.append(f"- {field}：{section.get(field, '')}")
        else:
            for field in ["AI画面提示词", "镜头运动", "人物动作", "产品露出方式", "字幕文案", "对白/口播", "负面提示词"]:
                lines.append(f"- {field}：{section.get(field, '')}")
        lines.append("")
    return "\n".join(lines).strip()


def _extract_formulas(references: List[Mapping[str, Any]]) -> List[str]:
    formulas = []
    for item in references:
        analysis = item.get("analysis_result") or {}
        structure = analysis.get("内容结构")
        insertion = analysis.get("卖点植入方式")
        if structure:
            formulas.append(str(structure))
        if insertion:
            formulas.append(f"卖点植入：{insertion}")
    return list(dict.fromkeys(formulas))[:6] or ["钩子 -> 痛点 -> 场景 -> 产品细节 -> 转化引导"]


def _reference_report(references: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    report = []
    for item in references:
        report.append(
            {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "platform": item.get("platform", ""),
                "source_url": item.get("source_url", ""),
                "category": item.get("category", ""),
                "content_type": item.get("content_type", ""),
                "analysis_result": item.get("analysis_result", {}),
            }
        )
    return report


def _reference_values(references: List[Mapping[str, Any]], field: str) -> List[str]:
    values = []
    for item in references:
        analysis = item.get("analysis_result") or {}
        value = analysis.get(field)
        if isinstance(value, list):
            values.extend(str(entry) for entry in value)
        elif value:
            values.append(str(value))
    return list(dict.fromkeys(values))


def _check_similarity(text: str, references: List[Mapping[str, Any]], rules: Mapping[str, Any]) -> Dict[str, Any]:
    max_chars = int(rules.get("max_reused_sentence_chars", 8))
    reused = []
    for item in references:
        for sentence in _split_sentences(str(item.get("original_copy") or "")):
            if len(sentence) > max_chars and sentence in text:
                reused.append(sentence)
    return {
        "is_too_similar": bool(reused),
        "reused_sentences": reused[:5],
        "note": "未发现完整句子复用。" if not reused else "发现参考原句复用，建议重新改写。",
    }


def _similarity_summary(variants: List[Mapping[str, Any]], references: List[Mapping[str, Any]]) -> str:
    if any(item.get("similarity_check", {}).get("is_too_similar") for item in variants):
        return "部分原创方案与参考文案存在完整句子复用，请重新生成或手动改写相关句子。"
    return "已按结构迁移方式生成，未复用参考文案中的完整句子；最终稿仍建议人工复核品牌专属表达。"


def _score_rewrite_output(product: ProductInfo, variants: List[Mapping[str, Any]], references: List[Mapping[str, Any]], risks) -> Dict[str, Any]:
    score = 72
    if len(variants) >= 3:
        score += 8
    if references:
        score += 6
    if all(not item.get("similarity_check", {}).get("is_too_similar") for item in variants):
        score += 8
    if product.script_mode == "ai_video" and all("AI画面提示词" in item.get("markdown", "") for item in variants):
        score += 4
    if product.script_mode == "live_action" and all("AI画面提示词" not in item.get("markdown", "") for item in variants):
        score += 4
    if risks:
        score -= min(15, len(risks) * 4)
    return {
        "score": max(0, min(100, score)),
        "suggestions": [
            "保留参考素材的结构逻辑，但已经替换为当前产品、人群、卖点和场景。",
            "上线前建议人工检查品牌语气、价格机制和平台禁用词。",
        ],
    }


def _original_hook(product: ProductInfo, category: str, angle: str, index: int) -> str:
    hooks = [
        f"别急着买{product.product_name}，先看它在{angle}里解决什么问题。",
        f"同样是{category}，为什么这次要先看真实使用场景？",
        f"如果你是{product.audience}，这个细节可能比参数更重要。",
        f"{product.product_name}不是换个说法种草，而是把使用理由讲清楚。",
        f"先看这个场景，再判断{product.product_name}适不适合你。",
    ]
    return hooks[index % len(hooks)]


def _category_conflict(category: str, product: ProductInfo, angle: str) -> str:
    if category == "冻品餐饮类":
        return f"高峰期最怕备菜拖慢出餐，{product.product_name}需要证明能帮后厨把流程变顺。"
    if category == "1688工厂定制类":
        return f"客户担心定制不透明、打样慢、交付不稳，所以要把{product.product_name}的流程拍清楚。"
    if category == "母婴纸品类":
        return f"家庭高频使用时，用户更在意触感、湿水表现和日常擦拭体验。"
    if category == "洗护个护类":
        return f"用户不是只听香氛和护理概念，而是要看到洗前困扰、使用过程和洗后状态。"
    return f"用户对{product.product_name}的顾虑，需要放进{angle}里用细节化解。"


def _product_placement(product: ProductInfo, category: str, index: int) -> str:
    placements = [
        f"先露出使用场景，再让{product.product_name}作为解决方案自然入镜。",
        f"用手部动作和产品特写承接{product.selling_points}，不直接喊夸张结论。",
        f"把{product.product_name}放在冲突被解决的关键动作里，而不是硬性口播植入。",
    ]
    return placements[index % len(placements)]


def _load_rules(path: Path) -> Dict[str, Any]:
    if path.exists():
        return load_yaml_like(path)
    return {}


def _split_sentences(text: str) -> List[str]:
    chunks = re.split(r"[\n。！？!?；;]+", text)
    return [chunk.strip(" ，,：:") for chunk in chunks if chunk.strip()]


def _format_value(value: Any) -> str:
    if isinstance(value, list):
        return "；".join(str(item) for item in value)
    return str(value)
