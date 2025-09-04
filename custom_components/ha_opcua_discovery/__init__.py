"""The asyncua integration."""

from __future__ import annotations

import asyncio
import functools
import logging
from datetime import timedelta
from typing import Any, Callable

from asyncua import Client, ua
from asyncua.common import ua_utils
from asyncua.ua import NodeClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_HUB_ID,
    CONF_HUB_URL,
    CONF_HUB_USERNAME,
    CONF_HUB_PASSWORD,
    CONF_HUB_SCAN_INTERVAL,
    CONF_HUB_ROOT_NODE,
    SERVICE_SET_VALUE,
    FIELD_NODE_HUB,
    FIELD_NODE_ID,
    FIELD_VALUE,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_VALUE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_NODE_HUB): cv.string,
        vol.Required(FIELD_NODE_ID): cv.string,
        vol.Required(FIELD_VALUE): vol.Any(
            float,
            int,
            str,
            cv.byte,
            cv.boolean,
            cv.time,
        ),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up asyncua from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    hub_id = entry.data[CONF_HUB_ID]

    hub = OpcuaHub(
        hub_name=hub_id,
        hub_url=entry.data[CONF_HUB_URL],
        root_node_id=entry.options.get(
            CONF_HUB_ROOT_NODE, entry.data.get(CONF_HUB_ROOT_NODE)
        ),
        username=entry.data.get(CONF_HUB_USERNAME),
        password=entry.data.get(CONF_HUB_PASSWORD),
    )

    coordinator = AsyncuaCoordinator(
        hass=hass,
        name=hub_id,
        hub=hub,
        update_interval_in_second=timedelta(
            seconds=entry.options.get(
                CONF_HUB_SCAN_INTERVAL,
                entry.data.get(CONF_HUB_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        ),
    )

    hass.data[DOMAIN][hub_id] = coordinator

    # Connect to the OPC-UA Server
    await hub.connect()

    # Fetch nodes from root node ID
    nodes = await hub.discover_nodes()
    coordinator.set_nodes(nodes)

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch"])

    async def _handle_set_value(service):
        try:
            hub_id_ = service.data.get(FIELD_NODE_HUB)
            if not hub_id_ or hub_id_ not in hass.data[DOMAIN]:
                raise HomeAssistantError(f"Hub '{hub_id_}' not found.")

            hub_ = hass.data[DOMAIN][hub_id_].hub
            node_id = service.data[FIELD_NODE_ID]
            value = service.data[FIELD_VALUE]

            success = await hub_.set_value(nodeid=node_id, value=value)
            if not success:
                raise HomeAssistantError(f"Failed to set value on node '{node_id}'.")

        except Exception as e:
            _LOGGER.exception("Service call to opcua_set_value failed")
            raise HomeAssistantError(f"Failed to call opcua_set_value: {e}")

    hass.services.async_register(
        domain=DOMAIN,
        service=f"{SERVICE_SET_VALUE}",
        service_func=_handle_set_value,
        schema=SERVICE_SET_VALUE_SCHEMA,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry and disconnect OPC UA client."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "switch"]
    )
    if unload_ok:
        hub_id = entry.data[CONF_HUB_ID]
        coordinator = hass.data[DOMAIN].pop(hub_id, None)
        if coordinator:
            await coordinator.hub.disconnect()
    return unload_ok


class OpcuaHub:
    """OPC UA Hub client."""

    def __init__(self, hub_name, hub_url, root_node_id, username=None, password=None):
        self._hub_name = hub_name
        self._hub_url = hub_url
        self._username = username
        self._password = password
        self.root_node_id = root_node_id
        self._monitor_task = None  # Track the monitor task

        self.device_info = DeviceInfo(configuration_url=hub_url)

        self.client = None  # Initially no client
        self._connected = False
        self._lock = asyncio.Lock()

    async def connect(self):
        async with self._lock:
            if self._connected:
                return True  # already connected
            try:
                self.client = Client(url=self._hub_url, timeout=5)
                if self._username:
                    self.client.set_user(self._username)
                if self._password:
                    self.client.set_password(self._password)
                await self.client.connect()
                self._connected = True
                _LOGGER.info("OPC UA client connected")
                return True
            except Exception as e:
                self._connected = False
                self.client = None
                _LOGGER.error(f"Failed to connect OPC UA client: {e}")
                return False  # <--- changed from raise

    async def disconnect(self):
        async with self._lock:
            if self._connected and self.client:
                try:
                    await self.client.disconnect()
                    _LOGGER.info("OPC UA client disconnected")
                except Exception as e:
                    _LOGGER.warning(f"Error during disconnect: {e}")
                finally:
                    self._connected = False
                    self.client = None

    async def safe_disconnect(self):
        try:
            await self.disconnect()
        except Exception as e:
            _LOGGER.debug(f"Safe disconnect failed: {e}")

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def ensure_connected(self) -> bool:
        if not self.is_connected:
            _LOGGER.debug("ensure_connected: not connected, connecting...")
            return await self.connect()
        return True

    @staticmethod
    def asyncua_wrapper(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            try:
                await self.ensure_connected()
                return await func(self, *args, **kwargs)

            except (asyncio.TimeoutError, ConnectionError) as e:
                _LOGGER.warning(f"Connection lost during OPC UA call: {e}")
                self._connected = False
                await self.safe_disconnect()

                # Try reconnect
                try:
                    await self.connect()
                except Exception as e2:
                    _LOGGER.error(f"Reconnect failed: {e2}")
                    raise

                # Retry once after reconnect
                return await func(self, *args, **kwargs)

            except asyncio.CancelledError:
                _LOGGER.info("OPCUA call cancelled.")
                raise

            except Exception as e:
                _LOGGER.exception(f"Unexpected error during OPC UA call: {e}")
                self._connected = False
                raise

        return wrapper

    @asyncua_wrapper
    async def is_writable_boolean(self, node_id: str) -> bool:
        try:
            node = self.client.get_node(node_id)
            node_class = await node.read_node_class()
            if node_class != NodeClass.Variable:
                return False

            data_type_node = await node.read_data_type()
            data_type_node_obj = self.client.get_node(data_type_node)
            data_type_browse_name = await data_type_node_obj.read_browse_name()

            if data_type_browse_name.Name != "Boolean":
                return False

            # Read AccessLevel attribute
            access_level_dv = await node.read_attribute(ua.AttributeIds.AccessLevel)
            access_level = access_level_dv.Value.Value

            # Check if writable bit is set (bit 1 is writable)
            if (access_level & 0x02) == 0:
                return False

            return True

        except Exception as e:
            _LOGGER.warning(
                f"Failed to check if node {node_id} is writable boolean: {e}"
            )
            return False

    @asyncua_wrapper
    async def discover_nodes(self) -> list[dict[str, Any]]:
        """Recursively discover variable nodes under the provided root node."""
        discovered_nodes = []

        async def _recurse_node(node):
            try:
                node_class = await node.read_node_class()
                browse_name = await node.read_browse_name()
                node_id = node.nodeid.to_string()

                if node_class == NodeClass.Variable:
                    try:
                        value = await node.read_value()
                        if isinstance(value, (int, float, str, bool)):
                            discovered_nodes.append(
                                {
                                    "name": browse_name.Name,
                                    "node_id": node_id,
                                    "value": value,
                                }
                            )
                        else:
                            _LOGGER.warning(
                                f"Skipping node {node_id} ({browse_name.Name}) with unsupported value type: {type(value).__name__}"
                            )
                    except ua.UaStatusCodeError as err:
                        if err.code == ua.StatusCodes.BadNotReadable:
                            _LOGGER.warning(
                                f"Skipping unreadable node {node_id} ({browse_name.Name}): BadNotReadable"
                            )
                        else:
                            _LOGGER.warning(
                                f"UaStatusCodeError while reading node {node_id} ({browse_name.Name}): {err}"
                            )
                    except Exception as err:
                        _LOGGER.warning(
                            f"Error reading value from node {node_id} ({browse_name.Name}): {err}"
                        )

                # Always try to recurse into child nodes
                if (
                    node_class
                    in (
                        NodeClass.Object,
                        NodeClass.ObjectType,
                        NodeClass.VariableType,
                    )
                    or node_class == NodeClass.Variable
                ):
                    try:
                        children = await node.get_children()
                        for child in children:
                            await _recurse_node(child)
                    except Exception as err:
                        _LOGGER.warning(
                            f"Failed to get children for node {node_id} ({browse_name.Name}): {err}"
                        )

            except Exception as err:
                _LOGGER.warning(f"Error while processing node {node}: {err}")

        try:
            root_node = self.client.get_node(self.root_node_id)
            await _recurse_node(root_node)
        except Exception as e:
            _LOGGER.warning(
                f"Failed to start node discovery from root node {self.root_node_id}: {e}"
            )

        return discovered_nodes

    @asyncua_wrapper
    async def get_value(self, nodeid: str) -> Any:
        node = self.client.get_node(nodeid)
        return await node.read_value()

    @asyncua_wrapper
    async def get_values(self, node_key_pair: dict[str, str]) -> dict[str, Any]:
        if not node_key_pair:
            return {}

        result = {}
        for name, nodeid in node_key_pair.items():
            node = self.client.get_node(nodeid)
            try:
                node_class = await node.read_node_class()
                if node_class != NodeClass.Variable:
                    _LOGGER.debug(
                        f"Skipping node {nodeid} ({name}) because it is not a Variable (NodeClass={node_class.name})"
                    )
                    continue
                value = await node.read_value()
                result[name] = value
            except Exception as e:
                _LOGGER.warning(f"Skipping node {nodeid} ({name}) due to error: {e}")
                self._connected = False
                continue

        return result

    @asyncua_wrapper
    async def set_value(self, nodeid: str, value: Any) -> bool:
        node = self.client.get_node(nodeid)
        variant_type = await node.read_data_type_as_variant_type()

        # Convert value safely to UA variant
        variant = ua_utils.string_to_variant(
            value if isinstance(value, str) else str(value), variant_type
        )

        await node.write_value(ua.DataValue(variant))
        return True


class AsyncuaCoordinator(DataUpdateCoordinator):
    """Coordinator for managing OPC UA polling."""

    def __init__(
        self, hass, name, hub: OpcuaHub, update_interval_in_second=DEFAULT_SCAN_INTERVAL
    ):
        self._hub = hub
        self._node_key_pair = {}
        super().__init__(
            hass, _LOGGER, name=name, update_interval=update_interval_in_second
        )

    @property
    def hub(self) -> OpcuaHub:
        return self._hub

    @property
    def node_key_pair(self) -> dict:
        return self._node_key_pair

    def set_nodes(self, nodes: list[dict[str, Any]]):
        self._node_key_pair = {node["name"]: node["node_id"] for node in nodes}

    async def _async_update_data(self) -> dict[str, Any]:
        _LOGGER.debug("Coordinator fetching data…")
        try:
            # Ensure connected before fetching
            connected = await self._hub.ensure_connected()
            if not connected:
                _LOGGER.warning("Could not establish OPC UA connection")
                return {}  # return empty data instead of raising

            return await self._hub.get_values(self._node_key_pair)

        except (asyncio.TimeoutError, ConnectionError, asyncio.CancelledError) as e:
            _LOGGER.warning(f"Connection lost during update: {e}")
            self._hub._connected = False
            await self._hub.safe_disconnect()

            # Try reconnect
            connected = await self._hub.connect()
            if not connected:
                _LOGGER.error("Reconnect failed during update")
                return {}

            # Retry fetch once
            return await self._hub.get_values(self._node_key_pair)

        except Exception as e:
            _LOGGER.error(f"Unexpected error during data update: {e}")
            return {}  # return empty instead of raise
