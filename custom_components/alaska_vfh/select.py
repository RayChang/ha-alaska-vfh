"""Mode select for Alaska VFH."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MODES
from .coordinator import AlaskaConfigEntry, AlaskaCoordinator
from .entity import AlaskaEntity

PARALLEL_UPDATES = 1

MODE_BY_OPTION = {option: mode for mode, option in MODES.items()}

DESCRIPTION = SelectEntityDescription(
    key="mode", translation_key="mode", options=list(MODES.values())
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlaskaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the mode select."""
    async_add_entities([AlaskaModeSelect(entry.runtime_data)])


class AlaskaModeSelect(AlaskaEntity, SelectEntity):
    """Select the heater work mode."""

    def __init__(self, coordinator: AlaskaCoordinator) -> None:
        """Initialize the select."""
        super().__init__(coordinator, DESCRIPTION)

    @property
    def current_option(self) -> str | None:
        """Return the option for register 10; unknown values map to None."""
        return MODES.get(self.coordinator.data.mode)

    async def async_select_option(self, option: str) -> None:
        """Apply the chosen mode."""
        await self.coordinator.async_set_mode(MODE_BY_OPTION[option])
