"""Diagnostics for Alaska VFH."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import AlaskaConfigEntry

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AlaskaConfigEntry
) -> dict[str, Any]:
    """Return entry data and the last raw registers."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "firmware": coordinator.firmware,
        "work_time": coordinator.work_time,
        "raw_registers": {
            str(address): value for address, value in coordinator.raw_registers.items()
        },
        "state": asdict(coordinator.data) if coordinator.data else None,
    }
