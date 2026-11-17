# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path

import pytest

from webiq_market_briefing.config import load_azure_openai_settings


def test_load_azure_openai_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "azure_openai": {
                    "endpoint": "https://example.openai.azure.com/",
                    "deployment": "example-deployment",
                    "api_version": "example-version",
                }
            }
        ),
        encoding="utf-8",
    )

    settings = load_azure_openai_settings(config_path)

    assert settings.endpoint == "https://example.openai.azure.com/"
    assert settings.deployment == "example-deployment"
    assert settings.api_version == "example-version"
    assert settings.auth_mode == "api-key"


def test_load_azure_openai_settings_rejects_placeholders(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "azure_openai": {
                    "endpoint": "https://<your-resource>.openai.azure.com/",
                    "deployment": "example-deployment",
                    "api_version": "example-version",
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="endpoint placeholder"):
        load_azure_openai_settings(config_path)


@pytest.mark.parametrize("data", [[], None, 1, "text"])
def test_load_azure_openai_settings_rejects_non_object_root(tmp_path: Path, data) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_azure_openai_settings(config_path)


@pytest.mark.parametrize("auth_mode", ["api-key", "azure-cli", "invalid", None])
def test_model_auth_mode_is_explicit_and_validated(tmp_path: Path, auth_mode) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"azure_openai": {
        "endpoint": "https://example.openai.azure.com/",
        "deployment": "deployment",
        "api_version": "version",
        "auth_mode": auth_mode,
    }}), encoding="utf-8")
    if auth_mode in ("api-key", "azure-cli"):
        assert load_azure_openai_settings(config_path).auth_mode == auth_mode
    else:
        with pytest.raises(ValueError, match="auth_mode"):
            load_azure_openai_settings(config_path)
