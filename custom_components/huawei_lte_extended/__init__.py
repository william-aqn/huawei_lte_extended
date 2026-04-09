"""Huawei LTE Extended — SMS reading, events, and management."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import HuaweiLteSmsCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

SERVICE_GET_SMS_LIST = "get_sms_list"
SERVICE_DELETE_SMS = "delete_sms"
SERVICE_DELETE_ALL_SMS = "delete_all_sms"

SERVICE_SCHEMA_GET_SMS_LIST = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Optional("page", default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Optional("count", default=20): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=50)
        ),
    }
)

SERVICE_SCHEMA_DELETE_SMS = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Required("index"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)

SERVICE_SCHEMA_DELETE_ALL_SMS = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
    }
)


def _get_coordinator(
    hass: HomeAssistant, entry_id: str
) -> HuaweiLteSmsCoordinator:
    """Get coordinator by entry_id."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ValueError(f"Invalid config entry: {entry_id}")
    coordinator: HuaweiLteSmsCoordinator = entry.runtime_data
    return coordinator


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Huawei LTE Extended services."""

    async def handle_get_sms_list(call: ServiceCall) -> dict[str, Any]:
        """Handle get_sms_list service call."""
        coordinator = _get_coordinator(hass, call.data["entry_id"])
        if coordinator.is_router_suspended:
            return {"messages": []}
        messages = await coordinator.async_get_sms_list(
            page=call.data["page"],
            count=call.data["count"],
        )
        return {"messages": messages}

    async def handle_delete_sms(call: ServiceCall) -> None:
        """Handle delete_sms service call."""
        coordinator = _get_coordinator(hass, call.data["entry_id"])
        if not coordinator.is_router_suspended:
            await coordinator.async_delete_sms(call.data["index"])

    async def handle_delete_all_sms(call: ServiceCall) -> dict[str, Any]:
        """Handle delete_all_sms service call."""
        coordinator = _get_coordinator(hass, call.data["entry_id"])
        if coordinator.is_router_suspended:
            return {"deleted": 0}
        deleted = await coordinator.async_delete_all_sms()
        return {"deleted": deleted}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SMS_LIST,
        handle_get_sms_list,
        schema=SERVICE_SCHEMA_GET_SMS_LIST,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_SMS,
        handle_delete_sms,
        schema=SERVICE_SCHEMA_DELETE_SMS,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_ALL_SMS,
        handle_delete_all_sms,
        schema=SERVICE_SCHEMA_DELETE_ALL_SMS,
        supports_response=SupportsResponse.OPTIONAL,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Huawei LTE Extended from a config entry."""
    coordinator = HuaweiLteSmsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
