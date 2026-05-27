"""Heuristic quality scoring for generated ecommerce short-video scripts."""

from __future__ import annotations

from typing import Any, Dict, List

from .models import ProductInfo, ScriptResult


CATEGORY_KEYWORDS = {
    "洗护个护类": ["浴室", "发根", "头发", "泡沫", "护理", "梳妆台", "通勤"],
    "母婴纸品类": ["宝妈", "宝宝", "家庭", "擦拭", "亲子", "护理台", "湿水"],
    "冻品餐饮类": ["后厨", "餐饮", "厨师", "出餐", "备菜", "炒锅", "翻台"],
    "1688工厂定制类": ["工厂", "客户", "采购", "打包", "产线", "仓库", "定制"],
    "食品零食类": ["开袋", "追剧", "办公室", "分享", "口感", "零食", "囤货"],
    "家清日用品类": ["厨房", "水槽", "清洁", "收纳", "家务", "台面", "污渍"],
}

VISUAL_DETAIL_KEYWORDS = [
    "特写",
    "微距",
    "镜面",
    "反射",
    "柔光",
    "暖光",
    "自然光",
    "浅景深",
    "虚化",
    "色调",
    "构图",
    "背景",
    "台面",
    "质感",
    "慢镜",
]
SHOT_DETAIL_KEYWORDS = [
    "push-in",
    "pull-back",
    "close-up",
    "macro",
    "slow motion",
    "pan",
    "tracking",
    "handheld",
    "定格",
    "推近",
    "拉远",
    "俯拍",
    "侧脸",
    "镜头",
]
NATURAL_VOICEOVER_KEYWORDS = ["如果你也", "不用", "先", "可以", "适合", "不是", "一点", "日常"]
PRODUCT_PLACEMENT_KEYWORDS = ["自然露出", "同框", "包装", "瓶身", "标签", "角度", "字幕", "定格", "镜面", "台面"]
AI_READINESS_KEYWORDS = ["统一负面提示词", "连续性要求", "9:16", "镜头运动", "人物动作", "产品露出", "字幕", "对白/口播"]


def score_script(product: ProductInfo, result: ScriptResult) -> Dict[str, Any]:
    """Return a 0-100 director-style score with strengths and improvements."""

    text = _result_text(result)
    dimensions = {
        "结构完整性": _score_structure(result),
        "开头冲击力": _score_opening(result),
        "类目匹配度": _score_category_match(result.category, text),
        "剧情完整度": _score_story(result),
        "画面提示词具体程度": _score_visual_specificity(result),
        "台词自然度": _score_voiceover_naturalness(result),
        "镜头语言细节": _score_shot_language(result),
        "产品植入自然度": _score_product_placement(product, result),
        "AI视频可生成性": _score_video_readiness(result),
        "合规安全性": _score_compliance(result),
    }
    raw_score = round(sum(dimensions.values()) / (len(dimensions) * 10) * 100)
    score = min(100, max(0, raw_score))
    if result.risk_terms:
        score = min(score, dimensions["合规安全性"] * 10)
    strengths = _build_strengths(dimensions, result)
    improvements = _build_improvements(dimensions, result)
    return {
        "score": score,
        "dimensions": dimensions,
        "strengths": strengths,
        "improvements": improvements,
    }


def _score_opening(result: ScriptResult) -> int:
    first = result.scenes[0] if result.scenes else None
    opening = " ".join([result.hook, first.title if first else "", first.subtitle if first else "", first.plot if first else ""])
    score = 4
    if any(token in opening for token in ["？", "?", "最怕", "突然", "饭点", "出门前", "客户催", "一打喷嚏"]):
        score += 3
    if first and ("0-3秒" in first.title or "冲击力开篇" in first.title):
        score += 1
    if first and len(first.plot) >= 20:
        score += 1
    if first and _keyword_hits(first.plot + first.visual, ["疲惫", "焦虑", "微光", "镜前", "通勤", "订单", "催", "宝宝"]) >= 2:
        score += 1
    return min(score, 10)


def _score_structure(result: ScriptResult) -> int:
    score = 3
    if result.scenes:
        score += 2
    if len(result.scenes) == 4:
        score += 2
    if all(scene.title and scene.duration_seconds > 0 for scene in result.scenes):
        score += 1
    if all(scene.plot and scene.visual and scene.voiceover and scene.subtitle for scene in result.scenes):
        score += 2
    return min(score, 10)


def _score_category_match(category: str, text: str) -> int:
    keywords = CATEGORY_KEYWORDS.get(category, [])
    hits = sum(1 for keyword in keywords if keyword in text)
    return min(10, 4 + hits)


def _score_story(result: ScriptResult) -> int:
    score = 2
    if len(result.scenes) == 4:
        score += 2
    titles = " ".join(scene.title for scene in result.scenes)
    if all(token in titles for token in ["冲击力开篇", "冲突铺垫", "产品植入", "成交引导"]):
        score += 2
    if all(scene.plot and scene.voiceover and scene.subtitle for scene in result.scenes):
        score += 2
    story_text = " ".join(scene.plot for scene in result.scenes)
    if _keyword_hits(story_text, ["冲突", "焦虑", "提醒", "进入", "反转", "轻松", "成交", "从容", "确认"]) >= 3:
        score += 2
    return min(score, 10)


def _score_visual_specificity(result: ScriptResult) -> int:
    visuals = " ".join(scene.visual for scene in result.scenes)
    score = 3
    score += min(4, _keyword_hits(visuals, VISUAL_DETAIL_KEYWORDS))
    if _average_length(scene.visual for scene in result.scenes) >= 35:
        score += 2
    if all(scene.visual for scene in result.scenes):
        score += 1
    return min(score, 10)


def _score_voiceover_naturalness(result: ScriptResult) -> int:
    voiceovers = [scene.voiceover for scene in result.scenes if scene.voiceover]
    voiceover_text = " ".join(voiceovers)
    score = 3
    score += min(3, _keyword_hits(voiceover_text, NATURAL_VOICEOVER_KEYWORDS))
    if voiceovers and all(8 <= len(item) <= 80 for item in voiceovers):
        score += 2
    if any(token in voiceover_text for token in ["，", "。", "——", "？"]):
        score += 1
    if not any(token in voiceover_text for token in ["全网", "保证", "立刻", "永久"]):
        score += 1
    return min(score, 10)


def _score_shot_language(result: ScriptResult) -> int:
    shot_text = " ".join(scene.shot for scene in result.scenes)
    visual_text = " ".join(scene.visual for scene in result.scenes)
    score = 3
    score += min(4, _keyword_hits(shot_text + " " + visual_text, SHOT_DETAIL_KEYWORDS))
    if all(scene.shot for scene in result.scenes):
        score += 1
    if _average_length(scene.shot for scene in result.scenes) >= 18:
        score += 2
    return min(score, 10)


def _score_product_placement(product: ProductInfo, result: ScriptResult) -> int:
    score = 3
    exposures = [scene.product_exposure for scene in result.scenes if scene.product_exposure]
    if len(exposures) >= len(result.scenes):
        score += 2
    if product.product_name in " ".join(exposures + [result.ai_video_prompt or ""]):
        score += 1
    exposure_text = " ".join(exposures)
    score += min(3, _keyword_hits(exposure_text, PRODUCT_PLACEMENT_KEYWORDS))
    if _average_length(exposures) >= 28:
        score += 1
    return min(score, 10)


def _score_video_readiness(result: ScriptResult) -> int:
    prompt = result.ai_video_prompt or ""
    scene_text = " ".join(
        " ".join([scene.visual, scene.shot, scene.character_action, scene.product_exposure, scene.subtitle, scene.voiceover])
        for scene in result.scenes
    )
    score = 2
    score += min(4, _keyword_hits(prompt + " " + scene_text, AI_READINESS_KEYWORDS))
    if result.metadata.get("unified_negative_prompt") or "统一负面提示词" in prompt:
        score += 1
    if result.metadata.get("continuity_requirements") or "连续性要求" in prompt:
        score += 1
    if all(scene.visual and scene.shot and scene.negative_prompt for scene in result.scenes):
        score += 2
    return min(score, 10)


def _score_compliance(result: ScriptResult) -> int:
    if not result.risk_terms:
        return 10
    penalty = min(9, len(result.risk_terms) * 3)
    return max(1, 10 - penalty)


def _build_strengths(dimensions: Dict[str, int], result: ScriptResult) -> List[str]:
    strengths: List[str] = []
    if dimensions["类目匹配度"] >= 12:
        strengths.append("剧情元素与产品类目匹配，人物关系和场景没有跑偏。")
    if dimensions["剧情完整度"] >= 8:
        strengths.append("四段结构完整，包含冲突、植入和成交引导。")
    if dimensions["画面提示词具体程度"] >= 8:
        strengths.append("画面提示词具备明确空间、光线、动作和视觉细节。")
    if dimensions["台词自然度"] >= 8:
        strengths.append("口播表达自然，适合短视频节奏。")
    if dimensions["AI视频可生成性"] >= 8:
        strengths.append("AI 视频提示词包含镜头、动作、产品露出和字幕口播，便于直接生成。")
    if dimensions["合规安全性"] >= 10:
        strengths.append("本地合规扫描未命中高风险词。")
    return strengths or ["脚本基础结构完整，可以作为电商短视频初稿使用。"]


def _build_improvements(dimensions: Dict[str, int], result: ScriptResult) -> List[str]:
    improvements: List[str] = []
    if dimensions["开头冲击力"] < 8:
        improvements.append("开头可以加入更明确的高压场景或反差台词，提高前三秒停留。")
    if dimensions["画面提示词具体程度"] < 8:
        improvements.append("画面提示词可补充光线、构图、环境、质感和主体动作细节。")
    if dimensions["台词自然度"] < 8:
        improvements.append("口播可减少模板感，增加更像真人表达的短句和停顿。")
    if dimensions["产品植入自然度"] < 8:
        improvements.append("产品露出可增加包装、使用动作和结尾定格的连续设计。")
    if dimensions["合规安全性"] < 10:
        terms = "、".join(risk.term for risk in result.risk_terms)
        improvements.append(f"需要替换高风险表达：{terms}。")
    if dimensions["AI视频可生成性"] < 8:
        improvements.append("建议补充统一负面提示词、连续性要求和更明确的视频比例。")
    return improvements or ["后续可按具体品牌调性进一步强化台词记忆点和成交口令。"]


def _result_text(result: ScriptResult) -> str:
    chunks = [
        result.product_summary,
        result.hook,
        result.ai_video_prompt or "",
        " ".join(result.selling_points),
        " ".join(str(value) for value in result.metadata.values()),
    ]
    for scene in result.scenes:
        chunks.extend(
            [
                scene.title,
                scene.plot,
                scene.visual,
                scene.voiceover,
                scene.subtitle,
                scene.shot,
                scene.character_action,
                scene.product_exposure,
            ]
        )
    return "\n".join(chunks)


def _keyword_hits(text: str, keywords: List[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def _average_length(values) -> float:
    items = [value for value in values if value]
    if not items:
        return 0
    return sum(len(item) for item in items) / len(items)
