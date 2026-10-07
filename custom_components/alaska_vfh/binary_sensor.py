"""Problem binary sensor for Alaska VFH."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AlaskaConfigEntry, AlaskaCoordinator
from .entity import AlaskaEntity

PARALLEL_UPDATES = 0

DESCRIPTION = BinarySensorEntityDescription(
    key="problem",
    translation_key="problem",
    device_class=BinarySensorDeviceClass.PROBLEM,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlaskaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the problem sensor."""
    async_add_entities([AlaskaProblemSensor(entry.runtime_data)])


class AlaskaProblemSensor(AlaskaEntity, BinarySensorEntity):
    """On when the system or feedback status register reports a fault."""

    def __init__(self, coordinator: AlaskaCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, DESCRIPTION)

    @property
    def is_on(self) -> bool:
        """Return True when register 6 or 7 is non-zero."""
        data = self.coordinator.data
        return data.system_status != 0 or data.feedback_status != 0
