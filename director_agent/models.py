"""Data models used across generation, validation, and rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


SUPPORTED_SCRIPT_MODES = {"live_action", "ai_video"}
SUPPORTED_GENERATION_MODES = {
    "local_only",
    "local_plus_llm_polish",
    "llm_generate_with_local_compliance",
}


@dataclass
class ProductInfo:
    product_name: str
    category: str
    audience: str
    selling_points: str
    platform: str
    duration: int
    script_mode: str
    price_mechanism: str = ""
    script_style: str = ""
    ai_tool: str = ""
    script_subtype: str = ""
    aspect_ratio: str = ""
    video_style: str = ""
    character_setting: str = ""
    scene_setting: str = ""
    generation_mode: str = "llm_generate_with_local_compliance"

    def normalized(self) -> "ProductInfo":
        mode = self.script_mode.strip().lower()
        if mode not in SUPPORTED_SCRIPT_MODES:
            raise ValueError("script_mode must be live_action or ai_video")
        generation_mode = (self.generation_mode or "llm_generate_with_local_compliance").strip()
        if generation_mode not in SUPPORTED_GENERATION_MODES:
            raise ValueError("generation_mode must be llm_generate_with_local_compliance, local_plus_llm_polish, or local_only")
        return ProductInfo(
            product_name=self.product_name.strip(),
            category=self.category.strip(),
            audience=self.audience.strip(),
            selling_points=self.selling_points.strip(),
            platform=self.platform.strip(),
            duration=int(self.duration),
            script_mode=mode,
            price_mechanism=self.price_mechanism.strip(),
            script_style=self.script_style.strip(),
            ai_tool=self.ai_tool.strip(),
            script_subtype=self.script_subtype.strip(),
            aspect_ratio=self.aspect_ratio.strip(),
            video_style=self.video_style.strip(),
            character_setting=self.character_setting.strip(),
            scene_setting=self.scene_setting.strip(),
            generation_mode=generation_mode,
        )


@dataclass
class CategoryStrategy:
    category: str
    script_type: str
    core_angle: str
    scenes: List[str]
    proof_points: List[str]
    tone: str
    recommended_script_subtypes: List[str] = field(default_factory=list)
    recommended_personas: List[str] = field(default_factory=list)
    recommended_plot_styles: List[str] = field(default_factory=list)
    recommended_ai_styles: List[str] = field(default_factory=list)
    safe_claims: List[str] = field(default_factory=list)
    avoid_claims: List[str] = field(default_factory=list)
    unsuitable_plot_styles: List[str] = field(default_factory=list)


@dataclass
class RiskTerm:
    term: str
    reason: str
    replacement: str
    count: int = 1


@dataclass
class Scene:
    order: int
    title: str
    visual: str
    voiceover: str
    subtitle: str
    shot: str
    duration_seconds: int
    plot: str = ""
    character_action: str = ""
    product_exposure: str = ""
    negative_prompt: str = ""


@dataclass
class ScriptResult:
    product_summary: str
    category: str
    strategy: Dict[str, Any]
    script_mode: str
    hook: str
    scenes: List[Scene]
    selling_points: List[str]
    ai_video_prompt: Optional[str]
    compliance_notes: List[str]
    risk_terms: List[RiskTerm]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        payload: Dict[str, Any],
        category: str,
        strategy: Dict[str, Any],
        script_mode: str,
        risk_terms: Optional[List[RiskTerm]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ScriptResult":
        payload = dict(payload)
        payload_metadata = payload.pop("metadata", {})
        payload = validate_script_payload(payload)
        scenes_payload = payload.get("scenes")
        if not isinstance(scenes_payload, list) or not scenes_payload:
            raise ValueError("ScriptResult requires at least one scene")

        scenes: List[Scene] = []
        for index, item in enumerate(scenes_payload, start=1):
            if not isinstance(item, dict):
                raise ValueError("Each scene must be an object")
            scenes.append(
                Scene(
                    order=int(item.get("order") or index),
                    title=str(item.get("title") or f"镜头 {index}"),
                    plot=str(item.get("plot") or ""),
                    visual=str(item.get("visual") or ""),
                    voiceover=str(item.get("voiceover") or ""),
                    subtitle=str(item.get("subtitle") or ""),
                    shot=str(item.get("shot") or "中景"),
                    duration_seconds=int(item.get("duration_seconds") or 5),
                    character_action=str(item.get("character_action") or ""),
                    product_exposure=str(item.get("product_exposure") or ""),
                    negative_prompt=str(item.get("negative_prompt") or ""),
                )
            )

        selling_points = payload.get("selling_points") or []
        if isinstance(selling_points, str):
            selling_points = [selling_points]

        notes = payload.get("compliance_notes") or []
        if isinstance(notes, str):
            notes = [notes]

        result = cls(
            product_summary=str(payload.get("product_summary") or ""),
            category=category,
            strategy=strategy,
            script_mode=script_mode,
            hook=str(payload.get("hook") or ""),
            scenes=scenes,
            selling_points=[str(item) for item in selling_points],
            ai_video_prompt=payload.get("ai_video_prompt"),
            compliance_notes=[str(item) for item in notes],
            risk_terms=risk_terms or [],
            metadata=metadata or {},
        )
        if isinstance(payload_metadata, dict):
            result.metadata.update(payload_metadata)
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_summary": self.product_summary,
            "category": self.category,
            "strategy": self.strategy,
            "script_mode": self.script_mode,
            "hook": self.hook,
            "scenes": [scene.__dict__ for scene in self.scenes],
            "selling_points": self.selling_points,
            "ai_video_prompt": self.ai_video_prompt,
            "compliance_notes": self.compliance_notes,
            "risk_terms": [risk.__dict__ for risk in self.risk_terms],
            "metadata": self.metadata,
        }


def validate_script_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate with Pydantic when installed, with manual checks as fallback."""

    try:
        from pydantic import BaseModel, ConfigDict, Field
    except ModuleNotFoundError:
        return payload

    class ScenePayload(BaseModel):
        model_config = ConfigDict(extra="forbid")

        order: int
        title: str
        plot: str = ""
        visual: str
        voiceover: str
        subtitle: str
        shot: str
        duration_seconds: int
        character_action: str = ""
        product_exposure: str = ""
        negative_prompt: str = ""

    class ScriptPayload(BaseModel):
        model_config = ConfigDict(extra="forbid")

        product_summary: str
        hook: str
        scenes: List[ScenePayload] = Field(min_length=1)
        selling_points: List[str]
        ai_video_prompt: Optional[str]
        compliance_notes: List[str]

    return ScriptPayload.model_validate(payload).model_dump()


SCRIPT_RESULT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "product_summary",
        "hook",
        "scenes",
        "selling_points",
        "ai_video_prompt",
        "compliance_notes",
    ],
    "properties": {
        "product_summary": {"type": "string"},
        "hook": {"type": "string"},
        "scenes": {
            "type": "array",
            "minItems": 3,
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "order",
                    "title",
                    "visual",
                    "voiceover",
                    "subtitle",
                    "shot",
                    "duration_seconds",
                ],
                "properties": {
                    "order": {"type": "integer"},
                    "title": {"type": "string"},
                    "plot": {"type": "string"},
                    "visual": {"type": "string"},
                    "voiceover": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "shot": {"type": "string"},
                    "duration_seconds": {"type": "integer"},
                    "character_action": {"type": "string"},
                    "product_exposure": {"type": "string"},
                    "negative_prompt": {"type": "string"},
                },
            },
        },
        "selling_points": {
            "type": "array",
            "items": {"type": "string"},
        },
        "ai_video_prompt": {"type": ["string", "null"]},
        "compliance_notes": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}
