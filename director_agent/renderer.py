"""Markdown and JSON output rendering."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from .config import PROJECT_ROOT
from .models import ProductInfo, ScriptResult


def render_markdown(product: ProductInfo, result: ScriptResult) -> str:
    if _is_ai_drama_ad(product, result):
        return render_ai_drama_markdown(product, result)

    script_subtype = result.metadata.get("normalized_script_subtype") or result.metadata.get("script_subtype") or product.script_subtype or "未填写"
    style_label = "AI视频风格" if result.script_mode == "ai_video" else "拍摄/表达风格"
    lines = [
        f"# {product.product_name} 短视频脚本",
        "",
        "## 基本信息",
        "",
        f"- 产品名称：{product.product_name}",
        f"- 识别类目：{result.category}",
        f"- 目标人群：{product.audience}",
        f"- 平台：{product.platform}",
        f"- 视频时长：{product.duration} 秒",
        f"- 脚本模式：{result.script_mode}",
        f"- 脚本子类型：{script_subtype}",
        f"- 视频比例：{product.aspect_ratio or '未填写'}",
        f"- {style_label}：{result.metadata.get('video_style', product.video_style or product.script_style or '未填写')}",
        f"- 人物设定：{product.character_setting or '未填写'}",
        f"- 场景设定：{product.scene_setting or '未填写'}",
        f"- 价格机制：{product.price_mechanism or '未填写'}",
        f"- 脚本风格：{result.metadata.get('video_style', product.script_style or '未填写')}",
        f"- 生成来源：{result.metadata.get('generation_source', 'unknown')}",
        f"- Provider：{result.metadata.get('provider', 'unknown')}",
        f"- Generation Mode：{result.metadata.get('generation_mode', product.generation_mode or 'local_only')}",
        "",
        "## 创作策略",
        "",
        f"- 脚本类型：{result.strategy.get('script_type')}",
        f"- 核心角度：{result.strategy.get('core_angle')}",
        f"- 场景建议：{'、'.join(result.strategy.get('scenes', []))}",
        f"- 证明点：{'、'.join(result.strategy.get('proof_points', []))}",
        "",
        "## 开场钩子",
        "",
        result.hook,
        "",
        "## 分镜脚本",
        "",
    ]
    if result.script_mode == "ai_video":
        lines.insert(31, f"- AI 工具：{product.ai_tool or result.metadata.get('ai_tool', '未填写')}")
    for scene in result.scenes:
        if result.script_mode == "live_action":
            _append_live_action_scene(lines, scene, result)
        else:
            _append_ai_video_scene(lines, scene)

    if result.script_mode == "ai_video" and result.ai_video_prompt:
        lines.extend(
            [
                "## AI 视频可复制提示词",
                "",
                "```text",
                result.ai_video_prompt,
                "```",
                "",
            ]
        )

    lines.extend(["## 合规检查", ""])
    if result.risk_terms:
        for risk in result.risk_terms:
            lines.append(
                f"- 高风险词：{risk.term}（出现 {risk.count} 次）｜原因：{risk.reason}｜替代表达：{risk.replacement}"
            )
    else:
        lines.append("- 未命中内置高风险词。")

    if result.compliance_notes:
        lines.extend(["", "## 模型/模板合规备注", ""])
        for note in result.compliance_notes:
            lines.append(f"- {note}")

    fallback_reason = result.metadata.get("fallback_reason")
    if fallback_reason:
        lines.extend(["", "## 生成备注", "", f"- 使用本地 fallback：{fallback_reason}"])

    _append_quality_score(lines, result)
    return "\n".join(lines).strip() + "\n"


def _append_live_action_scene(lines: list, scene, result: ScriptResult) -> None:
    is_talking_head = result.metadata.get("live_action_format") == "talking_head"
    lines.extend([f"### {scene.order}. {scene.title}", ""])
    if is_talking_head:
        lines.extend(
            [
                f"- 口播内容：{scene.voiceover}",
                f"- 画面建议：{scene.visual}",
                f"- 字幕文案：{scene.subtitle}",
                f"- 镜头建议：{scene.shot}",
                f"- 时长：{scene.duration_seconds} 秒",
                "",
            ]
        )
        return

    detail = _live_action_detail_for_scene(result, scene.order)
    lines.extend(
        [
            f"- 画面描述：{scene.visual}",
            f"- 拍摄镜头：{scene.shot}",
            f"- 人物动作：{scene.character_action or '演员按场景完成自然演示动作。'}",
            f"- 台词/口播：{scene.voiceover}",
            f"- 字幕文案：{scene.subtitle}",
            f"- 道具：{detail.get('props', '产品、辅助展示道具')}",
            f"- 场景：{detail.get('scene', '真实拍摄场景')}",
            f"- 剪辑节奏：{detail.get('editing_rhythm', '开头快，中段稳，结尾定格产品。')}",
            f"- 结尾引导：{detail.get('closing_guidance', '引导收藏或按需求查看规格。')}",
            f"- 时长：{scene.duration_seconds} 秒",
            "",
        ]
    )


def _append_ai_video_scene(lines: list, scene) -> None:
    lines.extend(
        [
            f"### {scene.order}. {scene.title}",
            "",
            f"- AI画面提示词：{scene.visual}",
            f"- 镜头运动：{scene.shot}",
            f"- 人物动作：{scene.character_action}",
            f"- 产品露出方式：{scene.product_exposure}",
            f"- 字幕文案：{scene.subtitle}",
            f"- 对白/口播：{scene.voiceover}",
            f"- 负面提示词：{scene.negative_prompt}",
            f"- 时长：{scene.duration_seconds} 秒",
            "",
        ]
    )


def _live_action_detail_for_scene(result: ScriptResult, order: int) -> dict:
    details = result.metadata.get("live_action_details") or []
    if isinstance(details, list) and 0 <= order - 1 < len(details) and isinstance(details[order - 1], dict):
        return details[order - 1]
    return {}


def render_ai_drama_markdown(product: ProductInfo, result: ScriptResult) -> str:
    metadata = result.metadata
    lines = [
        f"# {product.product_name} AI剧情短剧广告脚本",
        "",
        f"产品：{product.product_name}",
        f"视频时长：{product.duration} 秒",
        f"视频类型：{metadata.get('video_type', product.script_subtype or 'AI剧情短剧广告')}",
        f"适合 AI 工具：{metadata.get('ai_tool', product.ai_tool or 'Seedance')}",
        f"generation_source：{metadata.get('generation_source', 'unknown')}",
        f"provider：{metadata.get('provider', 'unknown')}",
        f"generation_mode：{metadata.get('generation_mode', product.generation_mode or 'local_only')}",
        f"视频比例：{metadata.get('aspect_ratio', product.aspect_ratio or '9:16')}",
        f"视频风格：{metadata.get('video_style', product.video_style or product.script_style or '真实电商风')}",
        f"人物设定：{metadata.get('character_setting', product.character_setting or '目标用户')}",
        f"人物关系：{metadata.get('persona_relation', metadata.get('character_setting', product.character_setting or '目标用户'))}",
        f"场景设定：{metadata.get('scene_setting', product.scene_setting or '真实使用场景')}",
        f"核心痛点：{metadata.get('core_pain_point', result.hook)}",
        f"产品植入方式：{metadata.get('product_placement', '产品在痛点、使用、转化镜头中自然露出')}",
        f"合规表达建议：{metadata.get('compliance_suggestion', '使用体验化、场景化表达，避免夸大承诺。')}",
        "",
    ]
    style_adjustment = metadata.get("style_adjustment")
    if style_adjustment:
        lines.extend(["风格调整：", style_adjustment, ""])

    for scene in result.scenes:
        lines.extend(
            [
                scene.title,
                f"剧情：{scene.plot}",
                f"AI画面提示词：{scene.visual}",
                f"镜头运动：{scene.shot}",
                f"人物动作：{scene.character_action}",
                f"产品露出方式：{scene.product_exposure}",
                f"字幕文案：{scene.subtitle}",
                f"对白/口播：{scene.voiceover}",
                f"负面提示词：{scene.negative_prompt}",
                "",
            ]
        )

    lines.extend(
        [
            f"统一负面提示词：{metadata.get('unified_negative_prompt', '')}",
            f"连续性要求：{metadata.get('continuity_requirements', '')}",
            "",
            "可直接复制版提示词：",
            "```text",
            result.ai_video_prompt or "",
            "```",
            "",
            "## 合规检查",
            "",
        ]
    )
    if result.risk_terms:
        for risk in result.risk_terms:
            lines.append(
                f"- 高风险词：{risk.term}（出现 {risk.count} 次）｜原因：{risk.reason}｜替代表达：{risk.replacement}"
            )
    else:
        lines.append("- 未命中内置高风险词。")

    if result.compliance_notes:
        lines.extend(["", "## 模型/模板合规备注", ""])
        for note in result.compliance_notes:
            lines.append(f"- {note}")

    fallback_reason = result.metadata.get("fallback_reason")
    if fallback_reason:
        lines.extend(["", "## 生成备注", "", f"- 使用本地 fallback：{fallback_reason}"])
    _append_quality_score(lines, result)
    return "\n".join(lines).strip() + "\n"


def _append_quality_score(lines: list, result: ScriptResult) -> None:
    quality = result.metadata.get("quality_score") or {}
    if not isinstance(quality, dict) or "score" not in quality:
        return

    lines.extend(["", "## 脚本质量评分", "", f"- 总分：{quality.get('score')}/100"])

    dimensions = quality.get("dimensions") or {}
    if isinstance(dimensions, dict) and dimensions:
        lines.append("- 分项：")
        for name, score in dimensions.items():
            lines.append(f"  - {name}：{score}/15")

    strengths = quality.get("strengths") or []
    lines.extend(["", "### 优点"])
    if strengths:
        for item in strengths:
            lines.append(f"- {item}")
    else:
        lines.append("- 脚本结构完整，具备继续打磨的基础。")

    improvements = quality.get("improvements") or []
    if result.script_mode == "live_action":
        improvements = [
            item
            for item in improvements
            if "统一负面提示词" not in item and "连续性要求" not in item and "AI" not in item
        ]
    lines.extend(["", "### 需要优化的地方"])
    if improvements:
        for item in improvements:
            lines.append(f"- {item}")
    else:
        lines.append("- 可结合具体品牌调性进一步微调台词和成交口令。")


def _is_ai_drama_ad(product: ProductInfo, result: ScriptResult) -> bool:
    return (
        result.script_mode == "ai_video"
        and (
            product.script_subtype == "AI剧情短剧广告"
            or result.metadata.get("script_subtype") == "AI剧情短剧广告"
            or result.metadata.get("normalized_script_subtype") == "AI剧情短剧广告"
        )
    )


def write_outputs(
    product: ProductInfo,
    result: ScriptResult,
    output_dir: Optional[Path] = None,
    save_json: bool = True,
) -> Tuple[Path, Optional[Path]]:
    active_output_dir = output_dir or PROJECT_ROOT / "outputs"
    active_output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = sanitize_filename(product.product_name)
    basename = f"{timestamp}_{safe_name}_{product.script_mode}"

    markdown_path = active_output_dir / f"{basename}.md"
    markdown_path.write_text(render_markdown(product, result), encoding="utf-8")

    json_path = None
    if save_json:
        json_path = active_output_dir / f"{basename}.json"
        json_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return markdown_path, json_path


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", value.strip())
    return cleaned.strip("_") or "product"
