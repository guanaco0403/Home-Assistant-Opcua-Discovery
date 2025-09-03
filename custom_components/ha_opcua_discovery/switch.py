"""Switch platform for OPC UA."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AsyncuaCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: AsyncuaCoordinator = hass.data[DOMAIN][entry.data["hub_id"]]
    switches = []

    for name, node_id in coordinator.node_key_pair.items():
        # Skip nodes that are non-writable booleans
        is_writable_boolean = await coordinator.hub.is_writable_boolean(node_id)
        if not is_writable_boolean:
            continue
        switches.append(AsyncuaSwitch(coordinator, name, node_id))

    async_add_entities(switches)

class AsyncuaSwitch(CoordinatorEntity[AsyncuaCoordinator], SwitchEntity):
    """Representation of an OPC UA writable boolean switch."""

    def __init__(self, coordinator, name: str, node_id: str) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"opcua_{coordinator.name}_{name}"
        self._node_id = node_id
        self._is_on = False  # Default state

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        success = await self.coordinator.hub.set_value(self._node_id, True)
        if success:
            self._is_on = True
            self.async_write_ha_state()
        else:
            _LOGGER.error(f"Failed to turn on switch {self._attr_name}")

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        success = await self.coordinator.hub.set_value(self._node_id, False)
        if success:
            self._is_on = False
            self.async_write_ha_state()
        else:
            _LOGGER.error(f"Failed to turn off switch {self._attr_name}")

    @property
    def available(self) -> bool:
        """Return if the switch is available."""
        return super().available and self._attr_name in self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        value = self.coordinator.data.get(self._attr_name)
        if isinstance(value, bool):
            self._is_on = value
        self.async_write_ha_state()
