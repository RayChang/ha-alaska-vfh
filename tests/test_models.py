"""Table-driven tests for the model profiles (no Home Assistant needed).

Expected values are written out literally from the manufacturers' manuals.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).parent.parent / "custom_components" / "alaska_vfh" / "models.py"
_spec = importlib.util.spec_from_file_location("alaska_models", _PATH)
assert _spec is not None and _spec.loader is not None
models = importlib.util.module_from_spec(_spec)
sys.modules["alaska_models"] = models
_spec.loader.exec_module(models)

KEYS = ["300bkp", "300brp", "300srp", "968sr", "968sk"]

MODES = {
    "300bkp": {
        1: "heat_high",
        2: "heat_dry",
        3: "cool_fast",
        4: "dry_eco",
        5: "vent_high",
        6: "vent_low",
        7: "vent_24h",
        12: "off",
    },
    "300brp": {
        1: "heat",
        2: "heat_dry",
        3: "dry_eco",
        4: "cool",
        5: "vent_low",
        6: "vent_high",
        7: "vent_24h",
        10: "off",
    },
    "300srp": {
        1: "heat_high",
        2: "heat_low",
        3: "heat_dry",
        4: "dry_eco",
        5: "cool_fast",
        6: "cool_slow",
        7: "vent_high",
        8: "vent_low",
        9: "vent_24h",
        10: "off",
    },
    "968sr": {
        1: "heat_high",
        2: "heat_low",
        3: "heat_dry",
        4: "dry_eco",
        5: "cool_fast",
        6: "cool_slow",
        7: "vent_high",
        8: "vent_low",
        9: "vent_24h",
        10: "off",
    },
    "968sk": {
        1: "heat_high",
        2: "heat_medium",
        3: "heat_dry",
        4: "cool_fast",
        5: "cool_slow",
        6: "dry_eco",
        7: "vent_high",
        8: "vent_low",
        9: "vent_24h",
        12: "off",
    },
}
OFF = {"300bkp": 12, "300brp": 10, "300srp": 10, "968sr": 10, "968sk": 12}
VENT_24H = {"300bkp": 7, "300brp": 7, "300srp": 9, "968sr": 9, "968sk": 9}
MAX_MINUTES = {
    "300bkp": {1: 480, 2: 480, 3: 480, 4: 480, 5: 480, 6: 480},
    "300brp": {1: 480, 2: 480, 3: 720, 4: 720, 5: 720, 6: 720},
    "300srp": {1: 480, 2: 480, 3: 480, 4: 720, 5: 720, 6: 720, 7: 480, 8: 480},
    "968sr": {1: 480, 2: 480, 3: 480, 4: 720, 5: 720, 6: 720, 7: 720, 8: 720},
    "968sk": {1: 480, 2: 480, 3: 480, 4: 480, 5: 480, 6: 480, 7: 480, 8: 480},
}
REG_FIRMWARE = {"300bkp": 4, "300brp": 5, "300srp": 5, "968sr": 4, "968sk": 4}
REG_RESET = {"300bkp": 12, "300brp": 12, "300srp": 14, "968sr": 12, "968sk": 12}
FEEDBACK = {
    "300bkp": {0: "ok", 1: "relay_fault", 2: "motor_open"},
    "300brp": {0: "ok", 1: "motor_open"},
    "300srp": {0: "ok", 1: "motor_open"},
    "968sr": {0: "ok", 1: "relay_fault", 2: "motor_open"},
    "968sk": {0: "ok", 1: "relay_fault", 2: "motor_open"},
}
POLL_COUNT = {"300bkp": 6, "300brp": 6, "300srp": 8, "968sr": 6, "968sk": 6}
SYSTEM_STATUS_PLAIN = ("ok", "temp_sensor_open", "overheat")
SYSTEM_STATUS_SRP = (
    "ok",
    "temp_sensor_open",
    "overheat_only",
    "filter_replace",
    "multiple_faults",
)


def test_profile_keys() -> None:
    assert list(models.PROFILES) == KEYS
    assert models.DEFAULT_MODEL == "300bkp"
    for key in KEYS:
        assert models.get_profile(key).key == key


@pytest.mark.parametrize("key", KEYS)
def test_profile_tables(key: str) -> None:
    profile = models.get_profile(key)
    assert dict(profile.modes) == MODES[key]
    assert list(profile.modes) == sorted(MODES[key])
    assert profile.mode_off == OFF[key]
    assert profile.mode_vent_24h == VENT_24H[key]
    assert dict(profile.mode_max_minutes) == MAX_MINUTES[key]
    assert profile.max_work_minutes == max(MAX_MINUTES[key].values())
    assert profile.reg_firmware == REG_FIRMWARE[key]
    assert profile.reg_reset == REG_RESET[key]
    assert dict(profile.feedback_status) == FEEDBACK[key]
    assert profile.poll_count == POLL_COUNT[key]
    assert profile.fc06_modes == {OFF[key], VENT_24H[key]}
    assert profile.option_to_mode == {v: k for k, v in MODES[key].items()}
    assert profile.has_heater_type == (key in ("968sr", "968sk"))
    assert profile.has_air_controls == (key == "300srp")
    assert profile.has_filter_reset == (key == "300srp")
    assert profile.info_block_read == (key == "300bkp")
    assert profile.experimental == (key != "300bkp")
    expected = SYSTEM_STATUS_SRP if key == "300srp" else SYSTEM_STATUS_PLAIN
    assert profile.system_status_options == expected


def test_labels() -> None:
    expected = {
        "300bkp": ("300BKP", "300BKP", "Alaska 300BKP"),
        "300brp": ("300BRP", "300BRP", "Alaska 300BRP"),
        "300srp": ("300SRP", "300SRP", "Alaska 300SRP"),
        "968sr": ("968SRN / 968SRP", "968SRN/968SRP", "Alaska 968SR"),
        "968sk": ("968SKN / 968SKP", "968SKN/968SKP", "Alaska 968SK"),
    }
    for key, (label, device_model, name) in expected.items():
        profile = models.get_profile(key)
        assert (profile.label, profile.device_model, profile.default_name) == (
            label,
            device_model,
            name,
        )


def test_encode_work_time() -> None:
    assert models.encode_work_time(1) == 0x0001
    assert models.encode_work_time(61) == 0x0101
    assert models.encode_work_time(480) == 0x0800
    assert models.encode_work_time(720) == 0x0C00


def _plan_cases() -> list[tuple[str, int]]:
    return [(key, mode) for key in KEYS for mode in MODES[key]]


@pytest.mark.parametrize(("key", "mode"), _plan_cases())
def test_plan_mode_write(key: str, mode: int) -> None:
    profile = models.get_profile(key)
    if mode in (OFF[key], VENT_24H[key]):
        for minutes in (0, 30, 9999):
            assert models.plan_mode_write(profile, mode, minutes) == ("fc06", mode)
        return
    limit = MAX_MINUTES[key][mode]
    assert models.plan_mode_write(profile, mode, 0) == ("fc16", [mode, 0x0001])
    assert models.plan_mode_write(profile, mode, 1) == ("fc16", [mode, 0x0001])
    assert models.plan_mode_write(profile, mode, 61) == ("fc16", [mode, 0x0101])
    assert models.plan_mode_write(profile, mode, limit) == (
        "fc16",
        [mode, 0x0800 if limit == 480 else 0x0C00],
    )
    assert models.plan_mode_write(profile, mode, 9999) == (
        "fc16",
        [mode, 0x0800 if limit == 480 else 0x0C00],
    )


def test_plan_mode_write_clamps_per_mode() -> None:
    brp = models.get_profile("300brp")
    assert models.plan_mode_write(brp, 2, 720) == ("fc16", [2, 0x0800])
    assert models.plan_mode_write(brp, 3, 720) == ("fc16", [3, 0x0C00])


@pytest.mark.parametrize(
    ("key", "mode"),
    [
        ("300bkp", 8),
        ("300bkp", 10),
        ("300bkp", 0),
        ("300brp", 12),
        ("300brp", 8),
        ("300srp", 12),
        ("300srp", 11),
        ("968sr", 12),
        ("968sk", 10),
        ("968sk", 11),
    ],
)
def test_plan_mode_write_foreign_mode(key: str, mode: int) -> None:
    with pytest.raises(ValueError):
        models.plan_mode_write(models.get_profile(key), mode, 30)


@pytest.mark.parametrize("key", ["300bkp", "300brp", "968sr", "968sk"])
def test_decode_system_status_plain(key: str) -> None:
    profile = models.get_profile(key)
    assert models.decode_system_status(profile, 0) == "ok"
    assert models.decode_system_status(profile, 1) == "temp_sensor_open"
    assert models.decode_system_status(profile, 2) == "overheat"
    for value in (3, 4, 255, 65535):
        assert models.decode_system_status(profile, value) is None


def test_decode_system_status_srp() -> None:
    profile = models.get_profile("300srp")
    assert models.decode_system_status(profile, 0) == "ok"
    assert models.decode_system_status(profile, 1) == "temp_sensor_open"
    assert models.decode_system_status(profile, 2) == "overheat_only"
    assert models.decode_system_status(profile, 4) == "filter_replace"
    for value in (3, 5, 6, 7):
        assert models.decode_system_status(profile, value) == "multiple_faults"
    for value in (8, 16, 255):
        assert models.decode_system_status(profile, value) is None


def test_decode_heater_type() -> None:
    assert models.decode_heater_type(1) == "ptc"
    assert models.decode_heater_type(2) == "carbon"
    assert models.decode_heater_type(0) is None
    assert models.decode_heater_type(3) is None
    assert models.decode_heater_type(None) is None


def test_air_tables() -> None:
    assert dict(models.AIR_ZONES) == {1: "off", 2: "diffuse", 3: "focus"}
    assert dict(models.AIR_DIRECTIONS) == {
        1: "deg_65",
        2: "deg_80",
        3: "deg_95",
        4: "deg_110",
        5: "deg_125",
        6: "swing",
    }
    assert (models.REG_AIR_ZONE, models.REG_AIR_DIRECTION) == (12, 13)


def test_remaining_minutes() -> None:
    bkp = models.get_profile("300bkp")
    assert models.remaining_minutes(bkp, 7, 1400, 0x0100) == 1400
    assert models.remaining_minutes(bkp, 1, 0, 0x0105) == 65
    assert models.remaining_minutes(bkp, 12, 0, 0) == 0
    srp = models.get_profile("300srp")
    assert models.remaining_minutes(srp, 9, 900, 0) == 900
    assert models.remaining_minutes(srp, 7, 0, 0x0200) == 120
    assert models.remaining_minutes(srp, 10, 5, 0x0200) == 0


def test_plan_mode_write_coerces_minutes_to_int() -> None:
    profile = models.get_profile("300bkp")
    assert models.plan_mode_write(profile, 1, 30.5) == ("fc16", [1, 0x001E])
