"""Buttons for Alaska VFH."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MODES
from .coordinator import AlaskaConfigEntry, AlaskaCoordinator
from .entity import AlaskaEntity

PARALLEL_UPDATES = 1

RESET_DESCRIPTION = ButtonEntityDescription(
    key="reset",
    translation_key="reset",
    entity_category=EntityCategory.CONFIG,
    entity_registry_enabled_default=False,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlaskaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one button per mode plus the reset button."""
    coordinator = entry.runtime_data
    entities: list[AlaskaEntity] = [
        AlaskaModeButton(coordinator, mode) for mode in MODES
    ]
    entities.append(AlaskaResetButton(coordinator))
    async_add_entities(entities)


class AlaskaModeButton(AlaskaEntity, ButtonEntity):
    """Start a work mode."""

    def __init__(self, coordinator: AlaskaCoordinator, mode: int) -> None:
        """Initialize the button for a mode."""
        super().__init__(
            coordinator,
            ButtonEntityDescription(key=f"mode_{mode}", translation_key=f"mode_{mode}"),
        )
        self._mode = mode

    async def async_press(self) -> None:
        """Select the mode (uses the current work time for modes 1-6)."""
        await self.coordinator.async_set_mode(self._mode)


class AlaskaResetButton(AlaskaEntity, ButtonEntity):
    """Reset the power board."""

    def __init__(self, coordinator: AlaskaCoordinator) -> None:
        """Initialize the reset button."""
        super().__init__(coordinator, RESET_DESCRIPTION)

    async def async_press(self) -> None:
        """Write the reset magic word."""
        await self.coordinator.async_reset()
