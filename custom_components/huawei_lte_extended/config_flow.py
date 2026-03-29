"""Config flow for Huawei LTE Extended integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_PARENT_ENTRY_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HUAWEI_LTE_DOMAIN,
)


class HuaweiLteExtendedConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Huawei LTE Extended."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        # Get all huawei_lte config entries
        huawei_entries = self.hass.config_entries.async_entries(HUAWEI_LTE_DOMAIN)
        if not huawei_entries:
            return self.async_abort(reason="no_huawei_entries")

        if user_input is not None:
            parent_entry_id = user_input[CONF_PARENT_ENTRY_ID]

            # Find the parent entry to get its unique_id
            parent_entry = self.hass.config_entries.async_get_entry(parent_entry_id)
            if parent_entry is None:
                errors["base"] = "parent_not_found"
            else:
                # Use parent's unique_id to ensure one extended entry per router
                await self.async_set_unique_id(
                    f"{DOMAIN}_{parent_entry.unique_id}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"{parent_entry.title} SMS",
                    data={
                        CONF_PARENT_ENTRY_ID: parent_entry_id,
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    },
                )

        # Build options from existing huawei_lte entries
        entry_options = [
            SelectOptionDict(
                value=entry.entry_id,
                label=entry.title or entry.data.get("url", entry.entry_id),
            )
            for entry in huawei_entries
        ]

        data_schema = vol.Schema(
            {
                vol.Required(CONF_PARENT_ENTRY_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=entry_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=15,
                        max=3600,
                        step=5,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
