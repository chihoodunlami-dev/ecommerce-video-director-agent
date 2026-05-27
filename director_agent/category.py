"""Category recognition and script strategy rules."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable, List

from .config import load_category_rules
from .models import CategoryStrategy


def normalize_category(category: str) -> str:
    value = category.strip()
    return value if value else _default_category()


def recognize_category(product_name: str, selling_points: str = "", user_category: str = "") -> str:
    if user_category.strip():
        return normalize_category(user_category)

    corpus = f"{product_name} {selling_points}".lower()
    for category, keywords in _category_keywords().items():
        if any(keyword.lower() in corpus for keyword in keywords):
            return category
    return _default_category()


def get_strategy(category: str) -> CategoryStrategy:
    strategies = _strategies()
    return strategies.get(category, strategies[_default_category()])


def split_selling_points(selling_points: str) -> List[str]:
    separators: Iterable[str] = ["，", ",", "、", ";", "；", "\n"]
    parts = [selling_points]
    for separator in separators:
        next_parts: List[str] = []
        for part in parts:
            next_parts.extend(part.split(separator))
        parts = next_parts
    return [part.strip() for part in parts if part.strip()]


@lru_cache(maxsize=1)
def _category_rules() -> dict:
    return load_category_rules()


def _default_category() -> str:
    return str(_category_rules().get("default_category", "通用电商类"))


@lru_cache(maxsize=1)
def _category_keywords() -> Dict[str, List[str]]:
    keywords: Dict[str, List[str]] = {}
    for item in _category_rules().get("categories", []):
        name = str(item["name"])
        keywords[name] = [str(keyword) for keyword in item.get("keywords", [])]
    return keywords


@lru_cache(maxsize=1)
def _strategies() -> Dict[str, CategoryStrategy]:
    strategies: Dict[str, CategoryStrategy] = {}
    for item in _category_rules().get("categories", []):
        name = str(item["name"])
        strategies[name] = CategoryStrategy(
            category=name,
            script_type=str(item["script_type"]),
            core_angle=str(item["core_angle"]),
            scenes=[str(scene) for scene in item.get("scenes", [])],
            proof_points=[str(point) for point in item.get("proof_points", [])],
            tone=str(item["tone"]),
            recommended_script_subtypes=[
                str(value) for value in item.get("recommended_script_subtypes", [])
            ],
            recommended_personas=[str(value) for value in item.get("recommended_personas", [])],
            recommended_plot_styles=[
                str(value) for value in item.get("recommended_plot_styles", [])
            ],
            recommended_ai_styles=[str(value) for value in item.get("recommended_ai_styles", [])],
            safe_claims=[str(value) for value in item.get("safe_claims", [])],
            avoid_claims=[str(value) for value in item.get("avoid_claims", [])],
            unsuitable_plot_styles=[
                str(value) for value in item.get("unsuitable_plot_styles", [])
            ],
        )
    return strategies
