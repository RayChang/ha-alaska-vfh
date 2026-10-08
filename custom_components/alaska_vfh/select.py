"""Selects for Alaska VFH."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AlaskaConfigEntry, AlaskaCoordinator
from .entity import AlaskaEntity
from .models import AIR_DIRECTIONS, AIR_ZONES

PARALLEL_UPDATES = 1

AIR_ZONE_DESCRIPTION = SelectEntityDescription(
    key="air_zone", translation_key="air_zone", options=list(AIR_ZONES.values())
)
AIR_DIRECTION_DESCRIPTION = SelectEntityDescription(
    key="air_direction",
    translation_key="air_direction",
    options=list(AIR_DIRECTIONS.values()),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlaskaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the mode select and, where the model has them, the air selects."""
    coordinator = entry.runtime_data
    entities: list[AlaskaEntity] = [AlaskaModeSelect(coordinator)]
    if coordinator.profile.has_air_controls:
        entities.append(AlaskaAirZoneSelect(coordinator))
        entities.append(AlaskaAirDirectionSelect(coordinator))
    async_add_entities(entities)


class AlaskaModeSelect(AlaskaEntity, SelectEntity):
    """Select the heater work mode."""

    def __init__(self, coordinator: AlaskaCoordinator) -> None:
        """Initialize the select with the options of the model."""
        super().__init__(
            coordinator,
            SelectEntityDescription(
                key="mode",
                translation_key="mode",
                options=list(coordinator.profile.modes.values()),
            ),
        )
        self._mode_by_option = coordinator.profile.option_to_mode

    @property
    def current_option(self) -> str | None:
        """Return the option for register 10; unknown values map to None."""
        return self.coordinator.profile.modes.get(self.coordinator.data.mode)

    async def async_select_option(self, option: str) -> None:
        """Apply the chosen mode."""
        await self.coordinator.async_set_mode(self._mode_by_option[option])


class AlaskaAirZoneSelect(AlaskaEntity, SelectEntity):
    """Select the air zone (300SRP)."""

    def __init__(self, coordinator: AlaskaCoordinator) -> None:
        """Initialize the select."""
        super().__init__(coordinator, AIR_ZONE_DESCRIPTION)

    @property
    def current_option(self) -> str | None:
        """Return the option for register 12; unknown values map to None."""
        value = self.coordinator.data.air_zone
        return None if value is None else AIR_ZONES.get(value)

    async def async_select_option(self, option: str) -> None:
        """Apply the chosen air zone."""
        value = next(v for v, key in AIR_ZONES.items() if key == option)
        await self.coordinator.async_set_air_zone(value)


class AlaskaAirDirectionSelect(AlaskaEntity, SelectEntity):
    """Select the air direction (300SRP)."""

    def __init__(self, coordinator: AlaskaCoordinator) -> None:
        """Initialize the select."""
        super().__init__(coordinator, AIR_DIRECTION_DESCRIPTION)

    @property
    def current_option(self) -> str | None:
        """Return the option for register 13; 0 (off) and unknown give None."""
        value = self.coordinator.data.air_direction
        return None if value is None else AIR_DIRECTIONS.get(value)

    async def async_select_option(self, option: str) -> None:
        """Apply the chosen air direction."""
        value = next(v for v, key in AIR_DIRECTIONS.items() if key == option)
        await self.coordinator.async_set_air_direction(value)
