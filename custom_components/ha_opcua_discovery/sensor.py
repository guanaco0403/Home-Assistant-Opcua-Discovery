"""Sensor platform for OPC UA."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AsyncuaCoordinator
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: AsyncuaCoordinator = hass.data[DOMAIN][entry.data["hub_id"]]
    sensors = []

    for name, node_id in coordinator.node_key_pair.items():
        # Skip nodes that are writable booleans (handled by switches)
        is_writable_boolean = await coordinator.hub.is_writable_boolean(node_id)
        if is_writable_boolean:
            continue
        sensors.append(AsyncuaSensor(coordinator, name, node_id))

    async_add_entities(sensors)

class AsyncuaSensor(CoordinatorEntity[AsyncuaCoordinator], SensorEntity):
    """Representation of an OPC UA sensor."""

    def __init__(self, coordinator, name: str, node_id: str) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"opcua_{coordinator.name}_{name}"
        self._node_id = node_id
        self._attr_state_class = None

    @property
    def state_class(self):
        """Return the state class based on the type of native_value."""
        value = self.native_value
        if isinstance(value, (int, float, bool)):
            return SensorStateClass.MEASUREMENT
        # You can add more conditions if needed for other state classes
        return None

    @property
    def native_value(self):
        return self.coordinator.data.get(self._attr_name)

    @property
    def available(self) -> bool:
        """Return if the switch is available."""
        return super().available and self._attr_name in self.coordinator.data