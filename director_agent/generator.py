"""Generation pipeline: rules first, LLM when available, local fallback always."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

from .category import get_strategy, recognize_category
from .compliance import check_compliance
from .config import load_settings
from .llm import LLMClient, LLMError, create_llm_client, get_schema
from .local_generator import build_local_script_payload
from .models import ProductInfo, ScriptResult
from .prompts import build_messages
from .script_scorer import score_script
from .script_modes import normalize_script_options


def generate_script(
    product_info: ProductInfo,
    settings: Optional[Dict[str, Any]] = None,
    llm_client: Optional[LLMClient] = None,
) -> ScriptResult:
    product, normalization_metadata = normalize_script_options(product_info.normalized())
    active_settings = settings or load_settings()
    category = recognize_category(product.product_name, product.selling_points, product.category)
    strategy = get_strategy(category).__dict__

    if _is_ai_drama_request(product):
        payload = build_local_script_payload(product, category, strategy)
        result = ScriptResult.from_dict(
            payload,
            category=category,
            strategy=strategy,
            script_mode=product.script_mode,
            metadata={
                "generation_source": "local_drama",
                "provider": "local",
                "generation_mode": "local_only",
                "requested_generation_mode": product.generation_mode,
                **normalization_metadata,
            },
        )
        if product.generation_mode == "local_plus_llm_polish":
            return _polish_local_result(product, category, strategy, result, active_settings, llm_client)
        if product.generation_mode == "llm_generate_with_local_compliance":
            result.metadata["fallback_reason"] = "llm_generate_with_local_compliance is reserved for a later version"
            result.metadata["requested_generation_mode"] = product.generation_mode
        return _finalize_result(product, result)

    client_error: Optional[str] = None
    client = llm_client
    if client is None:
        try:
            client = create_llm_client(active_settings)
        except LLMError as exc:
            client_error = str(exc)

    if client is not None:
        max_retries = int(active_settings.get("llm", {}).get("max_retries", 2))
        messages = build_messages(product, category, strategy)
        for attempt in range(max_retries + 1):
            try:
                payload = client.generate(messages, get_schema())
                result = ScriptResult.from_dict(
                    payload,
                    category=category,
                    strategy=strategy,
                    script_mode=product.script_mode,
                    metadata={
                        "generation_source": "llm",
                        "provider": client.provider_name,
                        "generation_mode": product.generation_mode,
                        "attempt": attempt + 1,
                        **normalization_metadata,
                    },
                )
                return _finalize_result(product, result)
            except Exception as exc:
                client_error = str(exc)
                if attempt < max_retries:
                    messages = messages + [
                        {
                            "role": "user",
                            "content": (
                                "上一次输出没有通过结构化校验。"
                                f"错误：{client_error}。"
                                "请只返回完整、合法、符合 Schema 的 JSON。"
                            ),
                        }
                    ]

    payload = build_local_script_payload(product, category, strategy)
    result = ScriptResult.from_dict(
        payload,
        category=category,
        strategy=strategy,
        script_mode=product.script_mode,
        metadata={
            "generation_source": "local_fallback",
            "provider": "local",
            "generation_mode": "local_only",
            "fallback_reason": client_error or "LLM provider is local",
            **normalization_metadata,
        },
    )
    return _finalize_result(product, result)


def _is_ai_drama_request(product: ProductInfo) -> bool:
    return product.script_mode == "ai_video" and product.script_subtype == "AI剧情短剧广告"


def _polish_local_result(
    product: ProductInfo,
    category: str,
    strategy: Dict[str, Any],
    local_result: ScriptResult,
    settings: Dict[str, Any],
    llm_client: Optional[LLMClient],
) -> ScriptResult:
    client_error: Optional[str] = None
    client = llm_client
    if client is None:
        try:
            client = create_llm_client(settings)
        except LLMError as exc:
            client_error = str(exc)

    if client is None:
        local_result.metadata["generation_mode"] = "local_only"
        local_result.metadata["requested_generation_mode"] = "local_plus_llm_polish"
        local_result.metadata["fallback_reason"] = client_error or "LLM provider is local"
        _log_llm_polish(f"skip provider=local model=none success=false reason={local_result.metadata['fallback_reason']}")
        return _finalize_result(product, local_result)

    llm_settings = settings.get("llm", {})
    max_retries = int(llm_settings.get("polish_max_retries", 0))
    messages = _build_polish_messages(product, category, strategy, local_result)
    provider_name = getattr(client, "provider_name", "unknown")
    model_name = getattr(client, "model", "unknown")
    request_chars = sum(len(message.get("content", "")) for message in messages)
    _log_llm_polish(
        f"call provider={provider_name} model={model_name} request_chars={request_chars} attempt_count={max_retries + 1}"
    )
    for attempt in range(max_retries + 1):
        try:
            _log_llm_polish(f"attempt={attempt + 1} provider={provider_name} model={model_name}")
            payload = client.generate(messages, get_schema())
            polished = ScriptResult.from_dict(
                payload,
                category=category,
                strategy=strategy,
                script_mode=product.script_mode,
                metadata={
                    **local_result.metadata,
                    "generation_source": "local_drama+llm_polish",
                    "provider": client.provider_name,
                    "generation_mode": "local_plus_llm_polish",
                    "requested_generation_mode": "local_plus_llm_polish",
                    "attempt": attempt + 1,
                    "llm_model": model_name,
                },
            )
            _validate_polished_result(local_result, polished)
            polished.compliance_notes = list(dict.fromkeys(polished.compliance_notes + ["已先本地生成，再由大模型在固定结构内润色，最终合规以本地扫描为准。"]))
            _log_llm_polish(f"success=true provider={provider_name} model={model_name} attempt={attempt + 1}")
            return _finalize_result(product, polished)
        except Exception as exc:
            client_error = str(exc)
            _log_llm_polish(f"success=false provider={provider_name} model={model_name} attempt={attempt + 1} reason={client_error}")
            if attempt < max_retries:
                messages = messages + [
                    {
                        "role": "user",
                        "content": (
                            "上一次润色结果没有通过结构或约束校验。"
                            f"错误：{client_error}。"
                            "请保留原始分镜数量、标题、顺序、时长、卖点和所有字段，只优化语言表达。"
                        ),
                    }
                ]

    local_result.metadata["generation_mode"] = "local_only"
    local_result.metadata["requested_generation_mode"] = "local_plus_llm_polish"
    local_result.metadata["fallback_reason"] = f"LLM polish failed: {client_error}"
    local_result.metadata["llm_provider"] = provider_name
    local_result.metadata["llm_model"] = model_name
    return _finalize_result(product, local_result)


def _build_polish_messages(
    product: ProductInfo,
    category: str,
    strategy: Dict[str, Any],
    local_result: ScriptResult,
) -> list:
    scenes = []
    for scene in local_result.scenes:
        scenes.append(
            {
                "order": scene.order,
                "title": scene.title,
                "duration_seconds": scene.duration_seconds,
                "plot": scene.plot,
                "visual": scene.visual,
                "voiceover": scene.voiceover,
                "subtitle": scene.subtitle,
                "shot": scene.shot,
                "character_action": scene.character_action,
                "product_exposure": scene.product_exposure,
                "negative_prompt": scene.negative_prompt,
            }
        )
    payload = {
        "product_summary": local_result.product_summary,
        "hook": local_result.hook,
        "scenes": scenes,
        "selling_points": local_result.selling_points,
        "ai_video_prompt": local_result.ai_video_prompt,
        "compliance_notes": local_result.compliance_notes,
    }
    compact_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    style_constraints = {
        "script_type": strategy.get("script_type"),
        "core_angle": strategy.get("core_angle"),
        "safe_claims": strategy.get("safe_claims", []),
        "avoid_claims": strategy.get("avoid_claims", []),
    }
    return [
        {
            "role": "system",
            "content": (
                "你是电商短视频编导的润色助手。你的任务是在不改变结构和业务约束的前提下，"
                "优化中文短剧广告脚本的语言、画面感、剧情张力和可生成视频程度。"
            ),
        },
        {
            "role": "developer",
            "content": (
                "只返回符合 JSON Schema 的 JSON。禁止改变产品类目、分镜数量、分镜标题、分镜顺序、"
                "每段 duration_seconds、产品卖点、输出字段、合规规则、统一负面提示词和连续性要求。"
                "可以润色 plot、visual、voiceover、subtitle、shot、character_action、product_exposure，并根据润色后的分镜重写 ai_video_prompt。"
                "不得新增高风险词、医疗功效、绝对化承诺、虚假价格或夸大宣传。"
                "返回 JSON 顶层只能包含 product_summary、hook、scenes、selling_points、ai_video_prompt、compliance_notes。"
                "每个 scenes item 只能包含 order、title、plot、visual、voiceover、subtitle、shot、duration_seconds、character_action、product_exposure、negative_prompt。"
                "严禁在 scenes item 内加入 ai_video_prompt 或任何额外字段。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"产品：{product.product_name}\n"
                f"类目：{category}\n"
                f"目标人群：{product.audience}\n"
                f"核心卖点：{product.selling_points}\n"
                f"平台：{product.platform}\n"
                f"视频时长：{product.duration} 秒\n"
                f"类目约束：{json.dumps(style_constraints, ensure_ascii=False, separators=(',', ':'))}\n"
                "请润色下面这份本地稳定生成的核心脚本 JSON，保持 scenes 的 order/title/duration_seconds 完全一致，"
                "selling_points 完全一致，并返回完整 Schema 所需字段：\n"
                f"{compact_payload}"
            ),
        },
    ]


def _validate_polished_result(local_result: ScriptResult, polished: ScriptResult) -> None:
    if len(local_result.scenes) != len(polished.scenes):
        raise ValueError("Polished result changed scene count")
    if local_result.selling_points != polished.selling_points:
        raise ValueError("Polished result changed selling points")
    for local_scene, polished_scene in zip(local_result.scenes, polished.scenes):
        if local_scene.order != polished_scene.order:
            raise ValueError("Polished result changed scene order")
        if local_scene.title != polished_scene.title:
            raise ValueError("Polished result changed scene title")
        if local_scene.duration_seconds != polished_scene.duration_seconds:
            raise ValueError("Polished result changed scene duration")


def _finalize_result(product: ProductInfo, result: ScriptResult) -> ScriptResult:
    result.risk_terms = _scan_result(product, result)
    result.metadata["quality_score"] = score_script(product, result)
    return result


def _log_llm_polish(message: str) -> None:
    print(f"[LLM_POLISH] {message}", file=sys.stderr)


def _scan_result(product: ProductInfo, result: ScriptResult):
    text_parts = [
        product.product_name,
        product.audience,
        product.selling_points,
        result.product_summary,
        result.hook,
        " ".join(result.selling_points),
        result.ai_video_prompt or "",
        str(result.metadata.get("unified_negative_prompt", "")),
        str(result.metadata.get("continuity_requirements", "")),
    ]
    for scene in result.scenes:
        text_parts.extend(
            [
                scene.title,
                scene.plot,
                scene.visual,
                scene.voiceover,
                scene.subtitle,
                scene.shot,
                scene.character_action,
                scene.product_exposure,
                scene.negative_prompt,
            ]
        )
    return check_compliance("\n".join(text_parts))
