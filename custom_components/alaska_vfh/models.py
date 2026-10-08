"""Heater model profiles for Alaska VFH.

Everything that differs between heater models lives here, as one ModelProfile per
protocol family. This module is pure Python (no Home Assistant, no pymodbus) so it
can be tested on its own.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

DEFAULT_MODEL = "300bkp"

MIN_WORK_MINUTES = 1
VENT24_MINUTES = 1440

# Registers 0..5 form the identification block (300BKP reads it in one request)
INFO_BLOCK_COUNT = 6
# Register 5 holds the heater element type on the 968 models
REG_HEATER_TYPE = 5
# Registers 12 and 13 are readable and writable on the 300SRP only
REG_AIR_ZONE = 12
REG_AIR_DIRECTION = 13

HEATER_TYPES: Mapping[int, str] = MappingProxyType({1: "ptc", 2: "carbon"})
AIR_ZONES: Mapping[int, str] = MappingProxyType({1: "off", 2: "diffuse", 3: "focus"})
# Value 0 (off) can be read but not written, so it is not an option
AIR_DIRECTIONS: Mapping[int, str] = MappingProxyType(
    {
        1: "deg_65",
        2: "deg_80",
        3: "deg_95",
        4: "deg_110",
        5: "deg_125",
        6: "swing",
    }
)

_SYSTEM_STATUS: Mapping[int, str] = MappingProxyType(
    {0: "ok", 1: "temp_sensor_open", 2: "overheat"}
)
_SYSTEM_STATUS_OPTIONS = tuple(_SYSTEM_STATUS.values())
# 300SRP: register 6 is a bit field (bit 0 sensor, bit 1 overheat, bit 2 filter)
_SYSTEM_STATUS_BITS: Mapping[int, str] = MappingProxyType(
    {0: "ok", 1: "temp_sensor_open", 2: "overheat_only", 4: "filter_replace"}
)
_SYSTEM_STATUS_BITS_OPTIONS = (*_SYSTEM_STATUS_BITS.values(), "multiple_faults")

_FEEDBACK_FULL: Mapping[int, str] = MappingProxyType(
    {0: "ok", 1: "relay_fault", 2: "motor_open"}
)
_FEEDBACK_MOTOR: Mapping[int, str] = MappingProxyType({0: "ok", 1: "motor_open"})


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """Protocol facts of one heater model family."""

    key: str
    label: str
    device_model: str
    default_name: str
    experimental: bool
    modes: Mapping[int, str]
    mode_off: int
    mode_vent_24h: int
    mode_max_minutes: Mapping[int, int]
    reg_firmware: int
    reg_reset: int
    feedback_status: Mapping[int, str]
    system_status_options: tuple[str, ...]
    system_status_bitfield: bool
    has_heater_type: bool
    has_air_controls: bool
    has_filter_reset: bool
    poll_count: int
    info_block_read: bool

    @property
    def fc06_modes(self) -> frozenset[int]:
        """Modes written with FC06; every other mode needs FC16."""
        return frozenset({self.mode_off, self.mode_vent_24h})

    @property
    def max_work_minutes(self) -> int:
        """Largest work time of any timed mode."""
        return max(self.mode_max_minutes.values())

    @property
    def option_to_mode(self) -> dict[str, int]:
        """Reverse lookup from option key to register 10 value."""
        return {option: mode for mode, option in self.modes.items()}


PROFILES: dict[str, ModelProfile] = {
    profile.key: profile
    for profile in (
        ModelProfile(
            key="300bkp",
            label="300BKP",
            device_model="300BKP",
            default_name="Alaska 300BKP",
            experimental=False,
            modes=MappingProxyType(
                {
                    1: "heat_high",
                    2: "heat_dry",
                    3: "cool_fast",
                    4: "dry_eco",
                    5: "vent_high",
                    6: "vent_low",
                    7: "vent_24h",
                    12: "off",
                }
            ),
            mode_off=12,
            mode_vent_24h=7,
            mode_max_minutes=MappingProxyType(dict.fromkeys(range(1, 7), 480)),
            reg_firmware=4,
            reg_reset=12,
            feedback_status=_FEEDBACK_FULL,
            system_status_options=_SYSTEM_STATUS_OPTIONS,
            system_status_bitfield=False,
            has_heater_type=False,
            has_air_controls=False,
            has_filter_reset=False,
            poll_count=6,
            info_block_read=True,
        ),
        ModelProfile(
            key="300brp",
            label="300BRP",
            device_model="300BRP",
            default_name="Alaska 300BRP",
            experimental=True,
            modes=MappingProxyType(
                {
                    1: "heat",
                    2: "heat_dry",
                    3: "dry_eco",
                    4: "cool",
                    5: "vent_low",
                    6: "vent_high",
                    7: "vent_24h",
                    10: "off",
                }
            ),
            mode_off=10,
            mode_vent_24h=7,
            mode_max_minutes=MappingProxyType(
                {1: 480, 2: 480, 3: 720, 4: 720, 5: 720, 6: 720}
            ),
            reg_firmware=5,
            reg_reset=12,
            feedback_status=_FEEDBACK_MOTOR,
            system_status_options=_SYSTEM_STATUS_OPTIONS,
            system_status_bitfield=False,
            has_heater_type=False,
            has_air_controls=False,
            has_filter_reset=False,
            poll_count=6,
            info_block_read=False,
        ),
        ModelProfile(
            key="300srp",
            label="300SRP",
            device_model="300SRP",
            default_name="Alaska 300SRP",
            experimental=True,
            modes=MappingProxyType(
                {
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
                }
            ),
            mode_off=10,
            mode_vent_24h=9,
            # The manual gives no limit for modes 7-8 and its limits overlap on
            # mode 3; the conservative value is used
            mode_max_minutes=MappingProxyType(
                {1: 480, 2: 480, 3: 480, 4: 720, 5: 720, 6: 720, 7: 480, 8: 480}
            ),
            reg_firmware=5,
            reg_reset=14,
            feedback_status=_FEEDBACK_MOTOR,
            system_status_options=_SYSTEM_STATUS_BITS_OPTIONS,
            system_status_bitfield=True,
            has_heater_type=False,
            has_air_controls=True,
            has_filter_reset=True,
            poll_count=8,
            info_block_read=False,
        ),
        ModelProfile(
            key="968sr",
            label="968SRN / 968SRP",
            device_model="968SRN/968SRP",
            default_name="Alaska 968SR",
            experimental=True,
            modes=MappingProxyType(
                {
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
                }
            ),
            mode_off=10,
            mode_vent_24h=9,
            mode_max_minutes=MappingProxyType(
                {1: 480, 2: 480, 3: 480, 4: 720, 5: 720, 6: 720, 7: 720, 8: 720}
            ),
            reg_firmware=4,
            reg_reset=12,
            feedback_status=_FEEDBACK_FULL,
            system_status_options=_SYSTEM_STATUS_OPTIONS,
            system_status_bitfield=False,
            has_heater_type=True,
            has_air_controls=False,
            has_filter_reset=False,
            poll_count=6,
            info_block_read=False,
        ),
        ModelProfile(
            key="968sk",
            label="968SKN / 968SKP",
            device_model="968SKN/968SKP",
            default_name="Alaska 968SK",
            experimental=True,
            modes=MappingProxyType(
                {
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
                }
            ),
            mode_off=12,
            mode_vent_24h=9,
            mode_max_minutes=MappingProxyType(dict.fromkeys(range(1, 9), 480)),
            reg_firmware=4,
            reg_reset=12,
            feedback_status=_FEEDBACK_FULL,
            system_status_options=_SYSTEM_STATUS_OPTIONS,
            system_status_bitfield=False,
            has_heater_type=True,
            has_air_controls=False,
            has_filter_reset=False,
            poll_count=6,
            info_block_read=False,
        ),
    )
}


def get_profile(key: str) -> ModelProfile:
    """Return the profile for a model key (KeyError for an unknown key)."""
    return PROFILES[key]


def encode_work_time(minutes: int) -> int:
    """Encode minutes as register 11 value: hours * 256 + minutes."""
    return (minutes // 60) * 256 + minutes % 60


type ModeWritePlan = tuple[Literal["fc06"], int] | tuple[Literal["fc16"], list[int]]


def plan_mode_write(profile: ModelProfile, mode: int, minutes: int) -> ModeWritePlan:
    """Choose the write function code for a mode; the only place this is decided.

    Stop and 24 h ventilation use FC06 with the mode value alone. Every timed mode
    uses FC16 with [mode, work_time], the time clamped to
    [MIN_WORK_MINUTES, the mode's maximum] and encoded as hours * 256 + minutes.
    """
    if mode not in profile.modes:
        raise ValueError(f"Unsupported mode {mode} for model {profile.key}")
    if mode in profile.fc06_modes:
        return ("fc06", mode)
    clamped = max(MIN_WORK_MINUTES, min(minutes, profile.mode_max_minutes[mode]))
    return ("fc16", [mode, encode_work_time(clamped)])


def decode_system_status(profile: ModelProfile, value: int) -> str | None:
    """Decode register 6 into an option key; unknown values give None."""
    if not profile.system_status_bitfield:
        return _SYSTEM_STATUS.get(value)
    if value in _SYSTEM_STATUS_BITS:
        return _SYSTEM_STATUS_BITS[value]
    if 0 < value < 8:
        return "multiple_faults"
    return None


def decode_heater_type(value: int | None) -> str | None:
    """Decode register 5 of the 968 models into an option key."""
    return None if value is None else HEATER_TYPES.get(value)


def remaining_minutes(
    profile: ModelProfile, mode: int, vent24_remaining: int, work_time_raw: int
) -> int:
    """Minutes left in the running mode.

    24 h ventilation counts down in register 9; timed modes use register 11
    (hi byte hours, lo byte minutes); any other mode (off) has none.
    """
    if mode == profile.mode_vent_24h:
        return vent24_remaining
    if mode in profile.mode_max_minutes:
        return (work_time_raw >> 8) * 60 + (work_time_raw & 0xFF)
    return 0
