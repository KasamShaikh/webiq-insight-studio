# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AzureOpenAISettings:
    endpoint: str
    deployment: str
    api_version: str
    auth_mode: str = "api-key"


def load_azure_openai_settings(path: Path) -> AzureOpenAISettings:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Configuration file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Configuration file is not valid JSON: {path}") from error

    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object.")
    azure_openai = data.get("azure_openai")
    if not isinstance(azure_openai, dict):
        raise ValueError("Configuration must contain an 'azure_openai' object.")

    auth_mode = azure_openai.get("auth_mode", "api-key")
    if auth_mode not in ("api-key", "azure-cli"):
        raise ValueError("azure_openai.auth_mode must be api-key or azure-cli.")
    return AzureOpenAISettings(
        endpoint=_required_setting(azure_openai, "endpoint"),
        deployment=_required_setting(azure_openai, "deployment"),
        api_version=_required_setting(azure_openai, "api_version"),
        auth_mode=auth_mode,
    )


def _required_setting(settings: dict[str, Any], name: str) -> str:
    value = settings.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"azure_openai.{name} must be a non-empty string.")
    if "<" in value or ">" in value:
        raise ValueError(
            f"Replace the azure_openai.{name} placeholder in config.json."
        )
    return value.strip()
