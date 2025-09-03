"""Config flow for Asyncua component."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import (
    CONF_NAME,
    CONF_URL,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_HUB_ID,
    CONF_HUB_URL,
    CONF_HUB_SCAN_INTERVAL,
    CONF_HUB_USERNAME,
    CONF_HUB_PASSWORD,
    CONF_HUB_ROOT_NODE,
)

DEFAULT_SCAN_INTERVAL = 10


class AsyncUAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AsyncUA integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            unique_id = user_input[CONF_NAME].lower()  # Normalize
            await self.async_set_unique_id(unique_id)
            if self._abort_if_unique_id_configured():
                # This will abort if a config with this unique_id already exists
                return self.async_abort(reason="already_configured")

            # Proceed normally
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_HUB_ID: user_input[CONF_NAME],
                    CONF_HUB_URL: user_input[CONF_URL],
                    CONF_HUB_USERNAME: user_input.get(CONF_USERNAME),
                    CONF_HUB_PASSWORD: user_input.get(CONF_PASSWORD),
                    CONF_HUB_SCAN_INTERVAL: user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                    CONF_HUB_ROOT_NODE: user_input.get(CONF_HUB_ROOT_NODE, "").strip(),
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_URL): str,
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
                vol.Optional(CONF_HUB_ROOT_NODE, default="ns=2;i=1"): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AsyncUAOptionsFlow(config_entry)


class AsyncUAOptionsFlow(config_entries.OptionsFlow):
    """Handle options for a config entry."""

    def __init__(self, config_entry):
        self._entry_id = config_entry.entry_id

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            root_node = user_input.get(CONF_HUB_ROOT_NODE, "").strip()
            scan_interval = user_input.get(
                CONF_HUB_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )

            # Update the options by creating the entry
            result = self.async_create_entry(
                title="",
                data={
                    CONF_HUB_SCAN_INTERVAL: scan_interval,
                    CONF_HUB_ROOT_NODE: root_node,
                },
            )

            # Schedule reload after returning the entry
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )

            return result

        current_scan_interval = self.config_entry.options.get(
            CONF_HUB_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_HUB_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        current_root_node = self.config_entry.options.get(
            CONF_HUB_ROOT_NODE,
            self.config_entry.data.get(CONF_HUB_ROOT_NODE, "ns=2;i=1"),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_HUB_SCAN_INTERVAL, default=current_scan_interval
                    ): int,
                    vol.Optional(CONF_HUB_ROOT_NODE, default=current_root_node): str,
                }
            ),
        )
