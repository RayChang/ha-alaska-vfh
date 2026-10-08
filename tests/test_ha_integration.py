"""Home Assistant level tests: config flow, migration and entity sets.

Run with: uv run --with pytest-homeassistant-custom-component --with pymodbus \
pytest tests -q. Skipped when pytest-homeassistant-custom-component is missing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import (  # noqa: E402
    MockConfigEntry,
)

import custom_components.alaska_vfh as integration  # noqa: E402

DOMAIN = "alaska_vfh"
BASE = {"host": "gateway", "port": 4196, "slave_id": 3}

# Entities per model, derived from the v0.1.0 entity set (17 for the 300BKP)
ENTITY_COUNT = {"300bkp": 17, "300brp": 17, "300srp": 22, "968sr": 20, "968sk": 20}


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from this repository."""


def _fake_hub() -> MagicMock:
    hub = MagicMock()
    hub.async_connect = AsyncMock()

    async def read(address: int, count: int, slave: int) -> list[int]:
        if address == 6:
            return [0, 0, 5, 0, 12, 0, 1, 2][:count]
        return [3, 1, 0, 0, 0x020B, 1][address : address + count]

    hub.async_read_holding_registers = AsyncMock(side_effect=read)
    hub.async_write_register = AsyncMock()
    hub.async_write_registers = AsyncMock()
    return hub


async def test_flow_asks_for_model(hass) -> None:
    hub = _fake_hub()
    with (
        patch(
            "custom_components.alaska_vfh.config_flow.async_acquire_hub",
            return_value=hub,
        ),
        patch("custom_components.alaska_vfh.config_flow.async_release_hub"),
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


async def test_migration_adds_model(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, version=1, minor_version=1, unique_id="a", data=BASE
    )
    entry.add_to_hass(hass)
    assert await integration.async_migrate_entry(hass, entry)
    assert entry.data["model"] == "300bkp"
    assert entry.minor_version == 2


async def test_migration_rejects_future_version(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=BASE)
    entry.add_to_hass(hass)
    assert not await integration.async_migrate_entry(hass, entry)


@pytest.mark.parametrize("model", list(ENTITY_COUNT))
async def test_entity_set(hass, model: str) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        unique_id=f"gateway:4196:3:{model}",
        data={**BASE, "model": model},
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.alaska_vfh.async_acquire_hub",
        return_value=_fake_hub(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entities) == ENTITY_COUNT[model]
    assert all(e.unique_id.startswith(f"{entry.entry_id}_") for e in entities)
