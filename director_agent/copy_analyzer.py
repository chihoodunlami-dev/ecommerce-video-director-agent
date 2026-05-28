"""Analyze manually supplied high-performing ecommerce copy references."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .config import PROJECT_ROOT, load_yaml_like


RULE_PATH = PROJECT_ROOT / "rules" / "copy_analysis_rules.json"


def analyze_reference_copy(reference: Mapping[str, Any]) -> Dict[str, Any]:
    """Extract reusable structure from a reference without preserving its wording."""

    rules = _load_rules()
    category = str(reference.get("category") or "通用类目")
    original_copy = str(reference.get("original_copy") or "")
    sentences = _split_sentences(original_copy)
    defaults = _category_defaults(rules, category)

    hook = _first_meaningful_line(original_copy)
    pain_points = _extract_by_keywords(sentences, defaults.get("pain_keywords", []), fallback=_fallback_pain(category))
    conversion = _extract_conversion(sentences, rules.get("conversion_keywords", []))
    scenes = _pick_scene_design(sentences, defaults.get("scenes", []))
    persona = _pick_first(defaults.get("persona_relations", []), "用户与种草者")
    reusable = _build_reusable_ideas(category, reference, defaults, rules)
    avoid = _avoid_exact_expressions(sentences)

    return {
        "开头钩子": hook,
        "用户痛点": pain_points,
        "目标人群": defaults.get("audience", "与该产品有明确使用需求的人群"),
        "场景设计": scenes,
        "人物关系": persona,
        "内容结构": _infer_content_structure(original_copy, rules),
        "卖点植入方式": _infer_selling_point_insertion(original_copy),
        "情绪触发点": defaults.get("emotions", ["痛点共鸣", "使用期待", "行动理由"]),
        "转化引导方式": conversion,
        "可复用思路": reusable,
        "不能照搬的表达": avoid,
        "适合迁移的产品类型": _suitable_product_types(category),
        "爆款公式": "钩子制造停留 -> 场景放大痛点 -> 产品以解决方案出现 -> 细节证明 -> 轻转化引导",
        "analysis_version": "v0.8-local",
    }


def _load_rules() -> Dict[str, Any]:
    if RULE_PATH.exists():
        return load_yaml_like(RULE_PATH)
    return {}


def _category_defaults(rules: Mapping[str, Any], category: str) -> Dict[str, Any]:
    categories = rules.get("category_defaults") or {}
    if category in categories:
        return dict(categories[category])
    return {
        "audience": "同类产品目标用户",
        "scenes": ["真实使用场景"],
        "persona_relations": ["用户与种草者"],
        "pain_keywords": ["问题", "痛点", "担心", "不方便"],
        "emotions": ["痛点共鸣", "真实体验", "下单理由"],
    }


def _split_sentences(text: str) -> List[str]:
    chunks = re.split(r"[\n。！？!?；;]+", text)
    return [chunk.strip(" ，,：:") for chunk in chunks if chunk.strip()]


def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:80]
    sentences = _split_sentences(text)
    return sentences[0][:80] if sentences else "用一个具体场景先抓住用户注意力"


def _extract_by_keywords(sentences: Iterable[str], keywords: Iterable[str], fallback: str) -> List[str]:
    matched = []
    for sentence in sentences:
        if any(keyword and keyword in sentence for keyword in keywords):
            matched.append(_generalize_sentence(sentence))
    return matched[:3] or [fallback]


def _extract_conversion(sentences: Iterable[str], keywords: Iterable[str]) -> str:
    for sentence in sentences:
        if any(keyword and keyword in sentence for keyword in keywords):
            return "用收藏、评论、咨询或查看规格承接兴趣，提醒用户按自身需求判断"
    return "用收藏、咨询、试用或查看规格引导用户做低门槛行动"


def _pick_scene_design(sentences: Iterable[str], scene_candidates: Iterable[str]) -> List[str]:
    scenes = [scene for scene in scene_candidates if any(scene in sentence for sentence in sentences)]
    if scenes:
        return scenes[:3]
    return list(scene_candidates)[:3] or ["真实使用场景"]


def _infer_content_structure(text: str, rules: Mapping[str, Any]) -> str:
    if any(word in text for word in ["对比", "之前", "现在", "使用前", "使用后"]):
        return "反差钩子 -> 使用前状态 -> 使用中细节 -> 使用后反馈 -> 下单理由"
    if any(word in text for word in ["老板", "工厂", "后厨", "采购"]):
        return "人群点名 -> 高频问题 -> 一步演示 -> 卖点拆解 -> 收藏/咨询"
    patterns = rules.get("structure_patterns") or []
    return _pick_first(patterns, "痛点开场 -> 场景冲突 -> 产品出现 -> 细节证明 -> 转化引导")


def _infer_selling_point_insertion(text: str) -> str:
    if any(word in text for word in ["测评", "对比", "实测"]):
        return "通过测评或对比镜头证明卖点，不直接夸大结果"
    if any(word in text for word in ["场景", "日常", "使用"]):
        return "把卖点放进真实使用场景，让用户自己看到价值"
    return "在痛点被放大后自然露出产品，再用细节镜头承接卖点"


def _build_reusable_ideas(
    category: str,
    reference: Mapping[str, Any],
    defaults: Mapping[str, Any],
    rules: Mapping[str, Any],
) -> List[str]:
    content_type = str(reference.get("content_type") or "短视频文案")
    return [
        f"沿用“先点出{category}用户高频困扰，再给出产品解决路径”的结构。",
        f"保留{content_type}的节奏感，但重写成当前产品自己的场景和卖点。",
        f"借鉴{_pick_first(defaults.get('persona_relations', []), '用户与种草者')}的人物关系张力。",
    ]


def _avoid_exact_expressions(sentences: List[str]) -> List[str]:
    avoid = []
    for sentence in sentences:
        if len(sentence) >= 10:
            avoid.append(sentence[:40])
        if len(avoid) >= 5:
            break
    return avoid or ["参考文案中的完整句子和独特表达不能照搬"]


def _suitable_product_types(category: str) -> List[str]:
    if category == "洗护个护类":
        return ["洗发水", "护发素", "沐浴露", "身体护理"]
    if category == "母婴纸品类":
        return ["乳霜纸", "湿巾", "棉柔巾", "家庭纸品"]
    if category == "冻品餐饮类":
        return ["冻品食材", "餐饮半成品", "后厨效率产品"]
    if category == "1688工厂定制类":
        return ["包装袋定制", "工厂定制", "小批量打样"]
    return [f"{category}相关产品", "同人群同场景产品"]


def _fallback_pain(category: str) -> str:
    return f"{category}用户在真实购买前需要被具体场景和细节说服"


def _generalize_sentence(sentence: str) -> str:
    sentence = re.sub(r"[0-9]+[%％]?", "具体数据", sentence)
    sentence = re.sub(r"全网最低|第一|唯一|最[^\s，,。！？]{0,4}", "更有吸引力", sentence)
    return sentence[:80]


def _pick_first(items: Any, fallback: str) -> str:
    if isinstance(items, list) and items:
        return str(items[0])
    return fallback
