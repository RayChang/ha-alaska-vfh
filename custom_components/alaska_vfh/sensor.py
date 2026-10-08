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

from .coordinator import AlaskaConfigEntry, AlaskaCoordinator
from .entity import AlaskaEntity
from .models import (
    HEATER_TYPES,
    ModelProfile,
    decode_heater_type,
    decode_system_status,
    remaining_minutes,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AlaskaSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor."""

    value_fn: Callable[[AlaskaCoordinator], int | str | None]


def _sensor_descriptions(profile: ModelProfile) -> list[AlaskaSensorDescription]:
    """Build the sensor descriptions for a model."""
    descriptions = [
        AlaskaSensorDescription(
            key="remaining_time",
            translation_key="remaining_time",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.MINUTES,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda c: remaining_minutes(
                c.profile,
                c.data.mode,
                c.data.vent24_remaining,
                c.data.work_time_raw,
            ),
        ),
        AlaskaSensorDescription(
            key="usage_hours",
            translation_key="usage_hours",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.HOURS,
            state_class=SensorStateClass.TOTAL_INCREASING,
            value_fn=lambda c: c.data.usage_hours,
        ),
        AlaskaSensorDescription(
            key="vent_24h_remaining",
            translation_key="vent_24h_remaining",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.MINUTES,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda c: c.data.vent24_remaining,
        ),
        AlaskaSensorDescription(
            key="system_status",
            translation_key="system_status",
            device_class=SensorDeviceClass.ENUM,
            options=list(profile.system_status_options),
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda c: decode_system_status(c.profile, c.data.system_status),
        ),
        AlaskaSensorDescription(
            key="feedback_status",
            translation_key="feedback_status",
            device_class=SensorDeviceClass.ENUM,
            options=list(profile.feedback_status.values()),
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda c: c.profile.feedback_status.get(c.data.feedback_status),
        ),
    ]
    if profile.has_heater_type:
        descriptions.append(
            AlaskaSensorDescription(
                key="heater_type",
                translation_key="heater_type",
                device_class=SensorDeviceClass.ENUM,
                options=list(HEATER_TYPES.values()),
                entity_category=EntityCategory.DIAGNOSTIC,
                value_fn=lambda c: decode_heater_type(c.heater_type),
            )
        )
    return descriptions


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlaskaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        AlaskaSensor(coordinator, desc)
        for desc in _sensor_descriptions(coordinator.profile)
    )


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
        return self.entity_description.value_fn(self.coordinator)
