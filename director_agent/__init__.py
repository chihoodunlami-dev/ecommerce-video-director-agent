"""Core package for the ecommerce video director agent."""

from .generator import generate_script
from .models import ProductInfo, ScriptResult

__all__ = ["ProductInfo", "ScriptResult", "generate_script"]

