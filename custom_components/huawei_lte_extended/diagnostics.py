"""Diagnostics support for Huawei LTE Extended."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import HUAWEI_LTE_DOMAIN

ENTRY_FIELDS_DATA_TO_REDACT = {
    "mac",
    "username",
    "password",
}
SMS_DATA_TO_REDACT = {
    "Phone",
    "Content",
    "Sca",
}
TO_REDACT = {
    *ENTRY_FIELDS_DATA_TO_REDACT,
    *SMS_DATA_TO_REDACT,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    parent_entry_id = entry.data.get("parent_entry_id")

    # Get parent router data if available
    parent_router_data: dict[str, Any] = {}
    huawei_data = hass.data.get(HUAWEI_LTE_DOMAIN)
    if huawei_data and parent_entry_id:
        router = huawei_data.routers.get(parent_entry_id)
        if router:
            parent_router_data = router.data

    return async_redact_data(
        {
            "entry": entry.data,
            "coordinator_data": coordinator.data,
            "parent_router_data": parent_router_data,
        },
        TO_REDACT,
    )
