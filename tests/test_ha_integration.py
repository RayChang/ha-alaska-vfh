"""Home Assistant level tests: config flow, migration and entity sets.

Run with: uv run --python 3.14 --with pytest-homeassistant-custom-component==0.13.325 \
--with pymodbus pytest tests -q -o asyncio_mode=auto
(that release brings Home Assistant 2026.4.4).
Skipped when pytest-homeassistant-custom-component is missing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.exceptions import HomeAssistantError  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import (  # noqa: E402
    MockConfigEntry,
)

import custom_components.alaska_vfh as integration  # noqa: E402
from custom_components.alaska_vfh.hub import AlaskaHubError  # noqa: E402

DOMAIN = "alaska_vfh"
BASE = {"host": "gateway", "port": 4196, "slave_id": 3}

# Entities per model (the 300BKP set is the literal v0.1.0 one, see below)
ENTITY_COUNT = {"300bkp": 17, "300brp": 17, "300srp": 22, "968sr": 20, "968sk": 20}

# unique_id suffixes of a v0.1.0 300BKP entry
V010_SUFFIXES = {
    "mode_1",
    "mode_2",
    "mode_3",
    "mode_4",
    "mode_5",
    "mode_6",
    "mode_7",
    "mode_12",
    "reset",
    "mode",
    "work_time",
    "remaining_time",
    "usage_hours",
    "vent_24h_remaining",
    "system_status",
    "feedback_status",
    "problem",
}

# Literal expectations from the manuals: mode numbers, stop, 24 h, reset register
MODE_NUMBERS = {
    "300bkp": [1, 2, 3, 4, 5, 6, 7, 12],
    "300brp": [1, 2, 3, 4, 5, 6, 7, 10],
    "300srp": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "968sr": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "968sk": [1, 2, 3, 4, 5, 6, 7, 8, 9, 12],
}
STOP = {"300bkp": 12, "300brp": 10, "300srp": 10, "968sr": 10, "968sk": 12}
VENT_24H = {"300bkp": 7, "300brp": 7, "300srp": 9, "968sr": 9, "968sk": 9}
RESET_REG = {"300bkp": 12, "300brp": 12, "300srp": 14, "968sr": 12, "968sk": 12}


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from this repository."""


def _fake_hub(mode: int = 0) -> MagicMock:
    hub = MagicMock()
    hub.async_connect = AsyncMock()

    async def read(address: int, count: int, slave: int) -> list[int]:
        if address == 6:
            return [0, 0, 5, 0, mode, 0, 1, 2][:count]
        return [3, 1, 0, 0, 0x020B, 1][address : address + count]

    hub.async_read_holding_registers = AsyncMock(side_effect=read)
    hub.async_write_register = AsyncMock()
    hub.async_write_registers = AsyncMock()
    return hub


def _patched(hub: MagicMock):
    """Patch the hub lookup of both the integration and the config flow."""
    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(
        patch("custom_components.alaska_vfh.async_acquire_hub", return_value=hub)
    )
    stack.enter_context(
        patch(
            "custom_components.alaska_vfh.config_flow.async_acquire_hub",
            return_value=hub,
        )
    )
    return stack


async def _setup(hass, model: str, hub: MagicMock, **extra) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        unique_id="gateway:4196:3",
        data={**BASE, "model": model},
        **extra,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _suffixes(hass, entry) -> set[str]:
    registry = er.async_get(hass)
    return {
        e.unique_id.removeprefix(f"{entry.entry_id}_")
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }


async def test_flow_asks_for_model(hass) -> None:
    hub = _fake_hub()
    with (
        _patched(hub),
        patch("custom_components.alaska_vfh.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "gateway", "port": 4196}
        )
        assert result["step_id"] == "model"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"model": "300srp"}
        )
        assert result["step_id"] == "device"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"name": "Heater", "slave_id": 3}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["model"] == "300srp"
    # Experimental models validate with a single-register read of register 0
    hub.async_read_holding_registers.assert_awaited_with(0, 1, 3)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert (entry.version, entry.minor_version) == (1, 2)
    assert entry.unique_id == "gateway:4196:3"


async def test_v010_entry_migrates_through_setup(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, version=1, minor_version=1, unique_id="gateway:4196:3", data=BASE
    )
    entry.add_to_hass(hass)
    with _patched(_fake_hub()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data["model"] == "300bkp"
    assert (entry.version, entry.minor_version) == (1, 2)
    assert _suffixes(hass, entry) == V010_SUFFIXES


async def test_future_major_version_is_not_migrated(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=BASE)
    entry.add_to_hass(hass)
    assert not await integration.async_migrate_entry(hass, entry)


async def test_unknown_model_fails_setup(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, version=1, minor_version=2, data={**BASE, "model": "999zz"}
    )
    entry.add_to_hass(hass)
    with _patched(_fake_hub()):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize("model", list(ENTITY_COUNT))
async def test_entity_set(hass, model: str) -> None:
    hub = _fake_hub()
    with _patched(hub):
        entry = await _setup(hass, model, hub)
        suffixes = _suffixes(hass, entry)
        assert len(suffixes) == ENTITY_COUNT[model]
        if model == "300bkp":
            assert suffixes == V010_SUFFIXES
        await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("model", list(MODE_NUMBERS))
async def test_mode_writes(hass, model: str) -> None:
    hub = _fake_hub()
    with _patched(hub):
        entry = await _setup(hass, model, hub)
        coordinator = entry.runtime_data
        for mode in MODE_NUMBERS[model]:
            hub.async_write_register.reset_mock()
            hub.async_write_registers.reset_mock()
            await coordinator.async_set_mode(mode)
            if mode in (STOP[model], VENT_24H[model]):
                hub.async_write_register.assert_awaited_once_with(10, mode, 3)
                hub.async_write_registers.assert_not_awaited()
            else:
                # default work time 30 min = 0x001E
                hub.async_write_registers.assert_awaited_once_with(
                    10, [mode, 0x001E], 3
                )
                hub.async_write_register.assert_not_awaited()
        hub.async_write_register.reset_mock()
        await coordinator.async_stop()
        hub.async_write_register.assert_awaited_once_with(10, STOP[model], 3)
        hub.async_write_register.reset_mock()
        await coordinator.async_reset()
        hub.async_write_register.assert_awaited_once_with(RESET_REG[model], 0xAA55, 3)
        hub.async_write_register.reset_mock()
        with pytest.raises(ValueError):
            await coordinator.async_set_mode(11)
        hub.async_write_register.assert_not_awaited()
        hub.async_write_registers.assert_not_awaited()
        await hass.config_entries.async_unload(entry.entry_id)


async def test_work_time_push_needs_fresh_running_mode(hass) -> None:
    hub = _fake_hub(mode=0)  # a fresh read says "no mode running"
    with _patched(hub):
        entry = await _setup(hass, "300brp", hub)
        coordinator = entry.runtime_data
        await coordinator.async_set_work_time(600)
        hub.async_write_registers.assert_not_awaited()
        hub.async_write_register.assert_not_awaited()
        assert coordinator.work_time == 600
        # mode 3 is a 720 minute mode on the 300BRP; 9999 is clamped to 720
        hub = _fake_hub(mode=3)
        coordinator.hub = hub
        await coordinator.async_set_work_time(9999)
        hub.async_write_registers.assert_awaited_once_with(10, [3, 0x0C00], 3)
        await hass.config_entries.async_unload(entry.entry_id)


async def test_model_specific_writes_are_guarded(hass) -> None:
    hub = _fake_hub()
    with _patched(hub):
        entry = await _setup(hass, "300bkp", hub)
        coordinator = entry.runtime_data
        for call in (
            coordinator.async_reset_filter(),
            coordinator.async_set_air_zone(2),
            coordinator.async_set_air_direction(1),
        ):
            with pytest.raises(HomeAssistantError):
                await call
        hub.async_write_register.assert_not_awaited()
        await hass.config_entries.async_unload(entry.entry_id)


async def test_300srp_air_and_filter_writes(hass) -> None:
    hub = _fake_hub()
    with _patched(hub):
        entry = await _setup(hass, "300srp", hub)
        coordinator = entry.runtime_data
        await coordinator.async_reset_filter()
        hub.async_write_register.assert_awaited_with(8, 0xAA55, 3)
        await coordinator.async_set_air_zone(3)
        hub.async_write_register.assert_awaited_with(12, 3, 3)
        await coordinator.async_set_air_direction(6)
        hub.async_write_register.assert_awaited_with(13, 6, 3)
        hub.async_write_register.reset_mock()
        for call in (
            coordinator.async_set_air_zone(0),
            coordinator.async_set_air_zone(4),
            coordinator.async_set_air_direction(0),
            coordinator.async_set_air_direction(7),
        ):
            with pytest.raises(HomeAssistantError):
                await call
        hub.async_write_register.assert_not_awaited()
        await hass.config_entries.async_unload(entry.entry_id)


async def test_gateway_exception_on_optional_read_fails_setup(hass) -> None:
    hub = _fake_hub()
    original = hub.async_read_holding_registers.side_effect

    async def read(address: int, count: int, slave: int) -> list[int]:
        if address == 5 and count == 1:
            raise AlaskaHubError("modbus", "gateway timeout", 0x0B)
        return await original(address, count, slave)

    hub.async_read_holding_registers = AsyncMock(side_effect=read)
    with _patched(hub):
        entry = MockConfigEntry(
            domain=DOMAIN, version=1, minor_version=2, data={**BASE, "model": "300brp"}
        )
        entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_exception_on_optional_read_is_tolerated(hass) -> None:
    hub = _fake_hub()
    original = hub.async_read_holding_registers.side_effect

    async def read(address: int, count: int, slave: int) -> list[int]:
        if address == 5 and count == 1:
            raise AlaskaHubError("modbus", "illegal address", 2)
        return await original(address, count, slave)

    hub.async_read_holding_registers = AsyncMock(side_effect=read)
    with _patched(hub):
        entry = await _setup(hass, "300brp", hub)
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.firmware is None
        await hass.config_entries.async_unload(entry.entry_id)


async def _reconfigure(hass, entry, **changes) -> dict:
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    data = {**BASE, "model": entry.data["model"], **changes}
    return await hass.config_entries.flow.async_configure(result["flow_id"], data)


async def test_reconfigure_host(hass) -> None:
    hub = _fake_hub()
    with _patched(hub):
        entry = await _setup(hass, "300bkp", hub)
        before = _suffixes(hass, entry)
        ids_before = {
            e.unique_id
            for e in er.async_entries_for_config_entry(
                er.async_get(hass), entry.entry_id
            )
        }
        result = await _reconfigure(hass, entry, host="Other-Gateway")
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert entry.data["host"] == "other-gateway"
        assert entry.unique_id == "other-gateway:4196:3"
        assert entry.state is ConfigEntryState.LOADED
        assert _suffixes(hass, entry) == before
        assert {
            e.unique_id
            for e in er.async_entries_for_config_entry(
                er.async_get(hass), entry.entry_id
            )
        } == ids_before
        await hass.config_entries.async_unload(entry.entry_id)


async def test_reconfigure_model(hass) -> None:
    hub = _fake_hub()
    with _patched(hub):
        entry = await _setup(hass, "300bkp", hub)
        result = await _reconfigure(hass, entry, model="968sk")
        await hass.async_block_till_done()
        assert result["reason"] == "reconfigure_successful"
        assert entry.data["model"] == "968sk"
        assert entry.runtime_data.profile.key == "968sk"
        # the 968SK validates with a single-register read of register 0
        hub.async_read_holding_registers.assert_any_await(0, 1, 3)
        assert "mode_9" in _suffixes(hass, entry)
        await hass.config_entries.async_unload(entry.entry_id)


async def test_reconfigure_collision_aborts(hass) -> None:
    hub = _fake_hub()
    with _patched(hub):
        entry = await _setup(hass, "300bkp", hub)
        other = MockConfigEntry(
            domain=DOMAIN,
            version=1,
            minor_version=2,
            unique_id="other:4196:3",
            data={**BASE, "host": "other", "model": "300bkp"},
        )
        other.add_to_hass(hass)
        result = await _reconfigure(hass, entry, host="other")
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        assert entry.data["host"] == "gateway"
        assert entry.unique_id == "gateway:4196:3"
        await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("side_effect", "error_key", "error"),
    [
        (AlaskaHubError("timeout", "no answer"), "base", "no_response"),
        (AlaskaHubError("connect", "refused"), "base", "cannot_connect"),
        (None, "slave_id", "invalid_slave"),
    ],
)
async def test_reconfigure_validation_failure_keeps_entry(
    hass, side_effect, error_key: str, error: str
) -> None:
    hub = _fake_hub()
    with _patched(hub):
        entry = await _setup(hass, "300bkp", hub)
        if side_effect is not None:
            hub.async_read_holding_registers = AsyncMock(side_effect=side_effect)
        else:
            # the device answers with a different id than the one entered
            hub.async_read_holding_registers = AsyncMock(return_value=[9] * 6)
        data_before = dict(entry.data)
        result = await _reconfigure(hass, entry, host="other", model="968sr")
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {error_key: error}
        assert dict(entry.data) == data_before
        assert entry.unique_id == "gateway:4196:3"
        await hass.config_entries.async_unload(entry.entry_id)
