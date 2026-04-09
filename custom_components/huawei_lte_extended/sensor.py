"""Sensor platform for Huawei LTE Extended."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PARENT_ENTRY_ID, DOMAIN, HUAWEI_LTE_DOMAIN
from .coordinator import HuaweiLteSmsCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Huawei LTE Extended sensors."""
    coordinator: HuaweiLteSmsCoordinator = entry.runtime_data
    async_add_entities([
        HuaweiLteExtendedLastSmsSensor(coordinator, entry),
    ])


class HuaweiLteExtendedLastSmsSensor(
    CoordinatorEntity[HuaweiLteSmsCoordinator], SensorEntity
):
    """Sensor showing the content of the most recently received SMS."""

    _attr_has_entity_name = True
    _attr_translation_key = "last_sms"
    _attr_icon = "mdi:message-text-outline"

    def __init__(
        self,
        coordinator: HuaweiLteSmsCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_last_sms"

        # Link to the parent huawei_lte device
        parent_entry_id = entry.data[CONF_PARENT_ENTRY_ID]
        parent_entry = self.coordinator.hass.config_entries.async_get_entry(
            parent_entry_id
        )
        if parent_entry and parent_entry.unique_id:
            self._attr_device_info = DeviceInfo(
                identifiers={(HUAWEI_LTE_DOMAIN, parent_entry.unique_id)},
            )

    @property
    def native_value(self) -> str | None:
        """Return the content of the latest SMS message."""
        if not self.coordinator.data:
            return None
        messages = self.coordinator.data.get("messages", [])
        if not messages:
            return None
        return messages[0]["content"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return phone, date, index, and read status of the latest SMS."""
        if not self.coordinator.data:
            return {}
        messages = self.coordinator.data.get("messages", [])
        if not messages:
            return {}
        latest = messages[0]
        return {
            "phone": latest["phone"],
            "date": latest["date"],
            "index": latest["index"],
            "read": latest["read"],
        }
