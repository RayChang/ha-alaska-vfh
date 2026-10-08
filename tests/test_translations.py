"""Check that the translation files match each other and the model profiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_models import models

_DIR = Path(__file__).parent.parent / "custom_components" / "alaska_vfh"
_FILES = ["strings.json", "translations/en.json", "translations/zh-Hant.json"]


def _load(name: str) -> dict:
    return json.loads((_DIR / name).read_text(encoding="utf-8"))


def _shape(node: object) -> object:
    if isinstance(node, dict):
        return {key: _shape(value) for key, value in node.items()}
    return None


def test_same_structure() -> None:
    shapes = [_shape(_load(name)) for name in _FILES]
    assert shapes[0] == shapes[1] == shapes[2]


def test_en_matches_strings() -> None:
    assert _load("strings.json") == _load("translations/en.json")


def test_v010_texts_unchanged() -> None:
    """The 300BKP button names must keep their v0.1.0 texts."""
    expected = {
        "en": {
            "mode_heat_high": "Mode: High heat",
            "mode_heat_dry": "Mode: Heat & dry",
            "mode_cool_fast": "Mode: Fast cool air",
            "mode_dry_eco": "Mode: Eco dry",
            "mode_vent_high": "Mode: Ventilation (high)",
            "mode_vent_low": "Mode: Ventilation (low)",
            "mode_vent_24h": "Mode: 24h ventilation",
            "mode_off": "Mode: Off",
        },
        "zh-Hant": {
            "mode_heat_high": "模式：高溫暖房",
            "mode_heat_dry": "模式：暖房乾燥",
            "mode_cool_fast": "模式：高速涼風",
            "mode_dry_eco": "模式：省電乾燥",
            "mode_vent_high": "模式：換氣強",
            "mode_vent_low": "模式：換氣弱",
            "mode_vent_24h": "模式：連續 24 小時換氣",
            "mode_off": "模式：停止",
        },
    }
    for lang, texts in expected.items():
        buttons = _load(f"translations/{lang}.json")["entity"]["button"]
        for key, text in texts.items():
            assert buttons[key]["name"] == text


@pytest.mark.parametrize("name", _FILES)
def test_keys_used_by_profiles_exist(name: str) -> None:
    data = _load(name)
    entity = data["entity"]
    for profile in models.PROFILES.values():
        assert profile.key in data["selector"]["model"]["options"]
        for option in profile.modes.values():
            assert f"mode_{option}" in entity["button"]
            assert option in entity["select"]["mode"]["state"]
        for option in profile.system_status_options:
            assert option in entity["sensor"]["system_status"]["state"]
        for option in profile.feedback_status.values():
            assert option in entity["sensor"]["feedback_status"]["state"]
    for option in models.AIR_ZONES.values():
        assert option in entity["select"]["air_zone"]["state"]
    for option in models.AIR_DIRECTIONS.values():
        assert option in entity["select"]["air_direction"]["state"]
    for option in models.HEATER_TYPES.values():
        assert option in entity["sensor"]["heater_type"]["state"]
    assert "filter_reset" in entity["button"]
    assert "model" in data["config"]["step"]
