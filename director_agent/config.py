"""Configuration loading helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_yaml_like(path: Path) -> Any:
    """Load YAML when available, otherwise load JSON-compatible YAML."""

    text = path.read_text(encoding="utf-8")
    try:
      import yaml  # type: ignore
    except ModuleNotFoundError:
      return json.loads(text)
    return yaml.safe_load(text)


def load_settings() -> Dict[str, Any]:
    return load_yaml_like(PROJECT_ROOT / "config" / "settings.yaml")


def load_compliance_rules() -> Dict[str, Any]:
    return load_yaml_like(PROJECT_ROOT / "rules" / "compliance.yaml")


def load_category_rules() -> Dict[str, Any]:
    return load_yaml_like(PROJECT_ROOT / "rules" / "category_rules.json")


def load_hook_rules() -> Dict[str, Any]:
    return load_yaml_like(PROJECT_ROOT / "rules" / "hook_rules.json")


def load_persona_rules() -> Dict[str, Any]:
    return load_yaml_like(PROJECT_ROOT / "rules" / "persona_rules.json")


def load_examples() -> Any:
    return load_yaml_like(PROJECT_ROOT / "examples" / "examples.yaml")
