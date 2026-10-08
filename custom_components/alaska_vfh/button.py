"""Buttons for Alaska VFH."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AlaskaConfigEntry, AlaskaCoordinator
from .entity import AlaskaEntity

PARALLEL_UPDATES = 1

RESET_DESCRIPTION = ButtonEntityDescription(
    key="reset",
    translation_key="reset",
    entity_category=EntityCategory.CONFIG,
    entity_registry_enabled_default=False,
)

FILTER_RESET_DESCRIPTION = ButtonEntityDescription(
    key="filter_reset",
    translation_key="filter_reset",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlaskaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one button per mode plus the reset button(s)."""
    coordinator = entry.runtime_data
    entities: list[AlaskaEntity] = [
        AlaskaModeButton(coordinator, mode, option)
        for mode, option in coordinator.profile.modes.items()
    ]
    entities.append(AlaskaResetButton(coordinator))
    if coordinator.profile.has_filter_reset:
        entities.append(AlaskaFilterResetButton(coordinator))
    async_add_entities(entities)


class AlaskaModeButton(AlaskaEntity, ButtonEntity):
    """Start a work mode."""

    def __init__(self, coordinator: AlaskaCoordinator, mode: int, option: str) -> None:
        """Initialize the button for a mode (the key stays the register value)."""
        super().__init__(
            coordinator,
            ButtonEntityDescription(
                key=f"mode_{mode}", translation_key=f"mode_{option}"
            ),
        )
        self._mode = mode

    async def async_press(self) -> None:
        """Select the mode (timed modes use the current work time)."""
        await self.coordinator.async_set_mode(self._mode)


class AlaskaResetButton(AlaskaEntity, ButtonEntity):
    """Reset the power board."""

    def __init__(self, coordinator: AlaskaCoordinator) -> None:
        """Initialize the reset button."""
        super().__init__(coordinator, RESET_DESCRIPTION)

    async def async_press(self) -> None:
        """Write the reset magic word."""
        await self.coordinator.async_reset()


class AlaskaFilterResetButton(AlaskaEntity, ButtonEntity):
    """Clear the "clean filter" message."""

    def __init__(self, coordinator: AlaskaCoordinator) -> None:
        """Initialize the filter reset button."""
        super().__init__(coordinator, FILTER_RESET_DESCRIPTION)

    async def async_press(self) -> None:
        """Write the reset magic word to the usage hours register."""
        await self.coordinator.async_reset_filter()
