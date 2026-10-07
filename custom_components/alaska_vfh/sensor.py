"""Sensors for Alaska VFH."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import FEEDBACK_STATUS, SYSTEM_STATUS
from .coordinator import AlaskaConfigEntry, AlaskaCoordinator, HeaterState
from .entity import AlaskaEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AlaskaSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor."""

    value_fn: Callable[[HeaterState], int | str | None]


SENSORS: tuple[AlaskaSensorDescription, ...] = (
    AlaskaSensorDescription(
        key="remaining_time",
        translation_key="remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.remaining_minutes,
    ),
    AlaskaSensorDescription(
        key="usage_hours",
        translation_key="usage_hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.usage_hours,
    ),
    AlaskaSensorDescription(
        key="vent_24h_remaining",
        translation_key="vent_24h_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.vent24_remaining,
    ),
    AlaskaSensorDescription(
        key="system_status",
        translation_key="system_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(SYSTEM_STATUS.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: SYSTEM_STATUS.get(data.system_status),
    ),
    AlaskaSensorDescription(
        key="feedback_status",
        translation_key="feedback_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(FEEDBACK_STATUS.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: FEEDBACK_STATUS.get(data.feedback_status),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlaskaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(AlaskaSensor(coordinator, desc) for desc in SENSORS)


class AlaskaSensor(AlaskaEntity, SensorEntity):
    """A heater sensor."""

    entity_description: AlaskaSensorDescription

    def __init__(
        self, coordinator: AlaskaCoordinator, description: AlaskaSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description)

    @property
    def native_value(self) -> int | str | None:
        """Return the decoded value."""
        return self.entity_description.value_fn(self.coordinator.data)
