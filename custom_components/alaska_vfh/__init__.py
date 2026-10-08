"""The Alaska Bath Heater (Modbus) integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import CONF_MODEL
from .coordinator import AlaskaConfigEntry, AlaskaCoordinator
from .hub import async_acquire_hub, async_release_hub
from .models import DEFAULT_MODEL

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]


async def async_migrate_entry(hass: HomeAssistant, entry: AlaskaConfigEntry) -> bool:
    """Migrate older entries: 1.1 had no model and was always a 300BKP."""
    if entry.version > 1:
        return False
    if entry.minor_version < 2:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_MODEL: DEFAULT_MODEL}, minor_version=2
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AlaskaConfigEntry) -> bool:
    """Set up a heater from a config entry."""
    hub = async_acquire_hub(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])
    coordinator = AlaskaCoordinator(hass, entry, hub)
    setup_ok = False
    try:
        try:
            await coordinator.async_read_device_info()
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            raise
        except HomeAssistantError as err:
            raise ConfigEntryNotReady(
                translation_domain=err.translation_domain,
                translation_key=err.translation_key,
                translation_placeholders=err.translation_placeholders,
            ) from err

        entry.runtime_data = coordinator

        device_info = coordinator.device_info
        dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers=device_info["identifiers"],
            name=device_info["name"],
            manufacturer=device_info["manufacturer"],
            model=device_info["model"],
            sw_version=device_info["sw_version"],
        )

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        setup_ok = True
    finally:
        if not setup_ok:
            async_release_hub(hass, hub)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AlaskaConfigEntry) -> bool:
    """Unload a config entry and release the shared gateway connection."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        async_release_hub(hass, entry.runtime_data.hub)
    return unloaded
