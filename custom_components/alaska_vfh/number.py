"""Work time number for Alaska VFH."""

from __future__ import annotations

from dataclasses import replace

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AlaskaConfigEntry, AlaskaCoordinator
from .entity import AlaskaEntity
from .models import MIN_WORK_MINUTES

PARALLEL_UPDATES = 1

DESCRIPTION = NumberEntityDescription(
    key="work_time",
    translation_key="work_time",
    device_class=NumberDeviceClass.DURATION,
    native_unit_of_measurement=UnitOfTime.MINUTES,
    native_min_value=MIN_WORK_MINUTES,
    native_step=1,
    mode=NumberMode.BOX,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlaskaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the work time number."""
    async_add_entities([AlaskaWorkTimeNumber(entry.runtime_data)])


class AlaskaWorkTimeNumber(AlaskaEntity, RestoreNumber):
    """Work time (minutes) used when a timed mode is started."""

    def __init__(self, coordinator: AlaskaCoordinator) -> None:
        """Initialize the number; the maximum is the largest limit of the model."""
        super().__init__(
            coordinator,
            replace(DESCRIPTION, native_max_value=coordinator.profile.max_work_minutes),
        )

    async def async_added_to_hass(self) -> None:
        """Restore the last chosen work time into the coordinator."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self.coordinator.work_time = max(
                MIN_WORK_MINUTES,
                min(int(last.native_value), self.coordinator.profile.max_work_minutes),
            )

    @property
    def native_value(self) -> float:
        """Return the shared work time."""
        return self.coordinator.work_time

    async def async_set_native_value(self, value: float) -> None:
        """Store the work time; push it when a timed mode is running."""
        await self.coordinator.async_set_work_time(int(value))
