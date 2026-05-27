"""LLM provider adapters and JSON parsing utilities."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, Dict, List, Optional

from .config import PROJECT_ROOT
from .models import SCRIPT_RESULT_SCHEMA


class LLMError(RuntimeError):
    """Raised when an LLM provider cannot return a valid script payload."""


class LLMClient(ABC):
    provider_name: str

    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Return a JSON-compatible script payload."""


def extract_json_payload(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LLMError("LLM response did not contain a JSON object")
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM response contained invalid JSON: {exc}") from exc


class HttpJsonClient:
    def __init__(self, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds

    def post_json(self, url: str, payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
        requests_response = self._post_json_with_requests(url, payload, api_key)
        if requests_response is not None:
            return requests_response

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_text = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise LLMError(f"LLM HTTP request failed: {exc}") from exc

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM HTTP response was not JSON: {exc}") from exc

    def _post_json_with_requests(self, url: str, payload: Dict[str, Any], api_key: str) -> Optional[Dict[str, Any]]:
        try:
            import requests  # type: ignore
        except ModuleNotFoundError:
            return None

        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(f"LLM HTTP request failed: {exc}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise LLMError(f"LLM HTTP response was not JSON: {exc}") from exc


class OpenAIResponsesClient(LLMClient):
    provider_name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str, timeout_seconds: int) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.http = HttpJsonClient(timeout_seconds)

    def generate(self, messages: List[Dict[str, str]], schema: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "input": messages,
            "temperature": 0.7,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "ecommerce_video_script",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        response = self.http.post_json(self.base_url, payload, self.api_key)
        text = _extract_openai_output_text(response)
        return extract_json_payload(text)


class DomesticCompatibleClient(LLMClient):
    provider_name = "domestic"

    def __init__(self, api_key: str, model: str, base_url: str, timeout_seconds: int) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.http = HttpJsonClient(timeout_seconds)

    def generate(self, messages: List[Dict[str, str]], schema: Dict[str, Any]) -> Dict[str, Any]:
        compatible_messages = []
        for message in messages:
            role = message["role"]
            if role == "developer":
                role = "system"
            compatible_messages.append({"role": role, "content": message["content"]})

        payload = {
            "model": self.model,
            "messages": compatible_messages,
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }
        response = self.http.post_json(self.base_url, payload, self.api_key)
        text = _extract_chat_completion_text(response)
        return extract_json_payload(text)


def create_llm_client(settings: Dict[str, Any]) -> Optional[LLMClient]:
    load_project_env()
    llm_settings = settings.get("llm", {})
    provider = str(llm_settings.get("provider", "local")).lower()
    timeout = int(llm_settings.get("timeout_seconds", 30))
    if provider == "local":
        return None

    if provider == "openai":
        openai_settings = llm_settings.get("openai", {})
        api_key_env = str(openai_settings.get("api_key_env", "OPENAI_API_KEY"))
        api_key = get_secret_value(api_key_env)
        if not api_key:
            raise LLMError(f"{api_key_env} is not set")
        return OpenAIResponsesClient(
            api_key=api_key,
            model=str(openai_settings.get("model", "gpt-4.1-mini")),
            base_url=str(openai_settings.get("base_url", "https://api.openai.com/v1/responses")),
            timeout_seconds=timeout,
        )

    if provider == "domestic":
        domestic_settings = llm_settings.get("domestic", {})
        api_key_env = str(domestic_settings.get("api_key_env", "DOMESTIC_LLM_API_KEY"))
        api_key = get_secret_value(api_key_env)
        base_url = str(domestic_settings.get("base_url", ""))
        if not api_key:
            raise LLMError(f"{api_key_env} is not set")
        if not base_url:
            raise LLMError("Domestic LLM base_url is not configured")
        return DomesticCompatibleClient(
            api_key=api_key,
            model=str(domestic_settings.get("model", "qwen-plus")),
            base_url=base_url,
            timeout_seconds=timeout,
        )

    raise LLMError(f"Unknown LLM provider: {provider}")


def get_secret_value(name: str) -> Optional[str]:
    """Read a secret from env first, then Streamlit Community Cloud secrets."""

    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st  # type: ignore

        secret_value = st.secrets.get(name)
    except Exception:
        return None
    if secret_value is None:
        return None
    return str(secret_value)


@lru_cache(maxsize=1)
def load_project_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _extract_openai_output_text(response: Dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]

    for output_item in response.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") in {"output_text", "text"} and isinstance(
                content_item.get("text"), str
            ):
                return content_item["text"]

    raise LLMError("OpenAI response did not include output text")


def _extract_chat_completion_text(response: Dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise LLMError("Chat completion response did not include choices")
    content = choices[0].get("message", {}).get("content")
    if not isinstance(content, str):
        raise LLMError("Chat completion response did not include message content")
    return content


def get_schema() -> Dict[str, Any]:
    return SCRIPT_RESULT_SCHEMA
