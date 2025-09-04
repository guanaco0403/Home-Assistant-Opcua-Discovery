"""Number platform for OPC UA."""

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AsyncuaCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AsyncuaCoordinator = hass.data[DOMAIN][entry.data["hub_id"]]
    numbers = []

    for name, node_id in coordinator.node_key_pair.items():
        # Check if node is a writable number
        is_writable_number = await coordinator.hub.is_writable_number(node_id)

        if not is_writable_number:
            continue

        numbers.append(AsyncuaNumber(coordinator, name, node_id))

    async_add_entities(numbers)


class AsyncuaNumber(CoordinatorEntity[AsyncuaCoordinator], NumberEntity):
    """Representation of an OPC UA writable number."""

    def __init__(self, coordinator, name: str, node_id: str) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"opcua_{coordinator.name}_{name}"
        self._node_id = node_id
        self._attr_native_min_value = 0
        self._attr_native_max_value = 10
        self._attr_native_step = 1  # You can make this configurable
        self._attr_native_unit_of_measurement = None  # Optional
        self._value = 0.0

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        success = await self.coordinator.hub.set_value(self._node_id, value)
        if success:
            self._value = value
            self.async_write_ha_state()
        else:
            _LOGGER.error(f"Failed to set number {self._attr_name} to {value}")

    @property
    def available(self) -> bool:
        """Return if the number is available."""
        return super().available and self._attr_name in self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        value = self.coordinator.data.get(self._attr_name)
        if isinstance(value, (int, float)):
            self._value = value
        self.async_write_ha_state()
