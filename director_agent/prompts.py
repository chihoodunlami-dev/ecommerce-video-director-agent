"""Prompt assembly for LLM-backed script generation."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .models import ProductInfo, SCRIPT_RESULT_SCHEMA


SYSTEM_PROMPT = (
    "你是一个电商短视频编导，擅长根据产品信息生成真实、可拍摄、"
    "转化导向且合规稳妥的短视频脚本。"
)


INSTRUCTION_PROMPT = (
    "只输出符合 JSON Schema 的 JSON，不要输出 Markdown。"
    "避免绝对化、医疗化、无法证明的效果承诺。"
    "live_action 要能直接指导拍摄；ai_video 要给出可复制的视频生成提示词，"
    "并包含画面提示词、镜头运动、人物动作、产品露出方式、字幕文案、口播文案、负面提示词。"
    "compliance_notes 只写概括性自查结论，不要逐字引用高风险词清单。"
)


def build_creative_brief(product: ProductInfo, category: str, strategy: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "product_name": product.product_name,
        "category": category,
        "audience": product.audience,
        "selling_points": product.selling_points,
        "platform": product.platform,
        "duration": product.duration,
        "script_mode": product.script_mode,
        "price_mechanism": product.price_mechanism,
        "script_style": product.script_style,
        "ai_tool": product.ai_tool,
        "script_subtype": product.script_subtype,
        "aspect_ratio": product.aspect_ratio,
        "video_style": product.video_style or product.script_style,
        "character_setting": product.character_setting,
        "scene_setting": product.scene_setting,
        "category_strategy": strategy,
        "output_rules": {
            "scene_count": "3-6",
            "language": "zh-CN",
            "compliance": "不要使用最强、第一、根治、永久、绝对、无副作用、100%等高风险表达。",
        },
    }


def build_messages(product: ProductInfo, category: str, strategy: Dict[str, Any]) -> List[Dict[str, str]]:
    brief = build_creative_brief(product, category, strategy)
    user_prompt = (
        "请根据以下创作 brief 生成电商短视频脚本 JSON。\n"
        f"{json.dumps(brief, ensure_ascii=False, indent=2)}\n\n"
        "必须满足这个 JSON Schema：\n"
        f"{json.dumps(SCRIPT_RESULT_SCHEMA, ensure_ascii=False)}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "developer", "content": INSTRUCTION_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
