"""Base entity for Alaska VFH."""

from __future__ import annotations

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AlaskaCoordinator


class AlaskaEntity(CoordinatorEntity[AlaskaCoordinator]):
    """Base class for all Alaska VFH entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AlaskaCoordinator, description: EntityDescription
    ) -> None:
        """Attach the entity to the shared device."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info
