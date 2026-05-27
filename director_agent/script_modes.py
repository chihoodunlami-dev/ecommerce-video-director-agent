"""Script mode option rules and normalization helpers."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Tuple

from .models import ProductInfo


LIVE_ACTION_SUBTYPES = [
    "真人口播",
    "真人剧情短剧",
    "测评对比",
    "直播切片",
    "老板口播",
    "探厂脚本",
    "产品使用教程",
]
AI_VIDEO_SUBTYPES = [
    "AI剧情短剧广告",
    "AI产品广告片",
    "AI生活方式种草",
    "AI虚拟人口播",
    "AI产品使用教程",
    "AI分镜提示词",
]
LIVE_ACTION_STYLES = [
    "真实口播风",
    "测评实拍风",
    "生活种草风",
    "老板讲解风",
    "直播切片风",
    "探厂纪实风",
    "教程演示风",
    "剧情短剧风",
]
AI_VIDEO_STYLES = [
    "霸总甜宠",
    "宝妈带娃",
    "职场逆袭",
    "高级浴室广告风",
    "厨房实拍风",
    "工厂探厂风",
    "高级产品广告风",
    "生活方式种草风",
]


def normalize_script_options(product: ProductInfo) -> Tuple[ProductInfo, Dict[str, Any]]:
    """Normalize illegal mode/subtype/style combinations before generation."""

    subtype = product.script_subtype or _default_subtype(product.script_mode)
    video_style = product.video_style or product.script_style or _default_style(product.script_mode)
    reason_parts = []

    if product.script_mode == "live_action":
        normalized_subtype = _normalize_live_action_subtype(subtype)
        normalized_style = video_style if video_style in LIVE_ACTION_STYLES else "真实口播风"
        ai_tool = ""
    else:
        normalized_subtype = _normalize_ai_video_subtype(subtype)
        normalized_style = video_style if video_style in AI_VIDEO_STYLES else "高级产品广告风"
        ai_tool = product.ai_tool

    if normalized_subtype != subtype:
        reason_parts.append(f"{product.script_mode} 不支持「{subtype}」，已改为「{normalized_subtype}」")
    if normalized_style != video_style:
        reason_parts.append(f"{product.script_mode} 不适合「{video_style}」，已改为「{normalized_style}」")
    if product.script_mode == "live_action" and product.ai_tool:
        reason_parts.append("真人实拍模式不使用 AI 工具字段，已忽略")

    normalized = replace(
        product,
        script_subtype=normalized_subtype,
        video_style=normalized_style,
        script_style=normalized_style,
        ai_tool=ai_tool,
    )
    metadata = {
        "normalized_script_subtype": normalized_subtype,
        "video_style": normalized_style,
        "normalization_reason": "；".join(reason_parts),
    }
    return normalized, metadata


def _default_subtype(script_mode: str) -> str:
    return "AI产品广告片" if script_mode == "ai_video" else "真人口播"


def _default_style(script_mode: str) -> str:
    return "高级产品广告风" if script_mode == "ai_video" else "真实口播风"


def _normalize_live_action_subtype(subtype: str) -> str:
    if subtype in LIVE_ACTION_SUBTYPES:
        return subtype
    mapping = {
        "AI剧情短剧广告": "真人剧情短剧",
        "AI产品广告片": "真人口播",
        "AI生活方式种草": "真人剧情短剧",
        "AI虚拟人口播": "真人口播",
        "AI产品使用教程": "产品使用教程",
        "AI分镜提示词": "真人口播",
        "真人剧情": "真人剧情短剧",
    }
    return mapping.get(subtype, "真人口播")


def _normalize_ai_video_subtype(subtype: str) -> str:
    if subtype in AI_VIDEO_SUBTYPES:
        return subtype
    mapping = {
        "真人口播": "AI虚拟人口播",
        "真人剧情": "AI剧情短剧广告",
        "真人剧情短剧": "AI剧情短剧广告",
        "测评对比": "AI产品广告片",
        "直播切片": "AI分镜提示词",
        "老板口播": "AI虚拟人口播",
        "探厂脚本": "AI分镜提示词",
        "产品使用教程": "AI产品使用教程",
    }
    return mapping.get(subtype, "AI分镜提示词")
