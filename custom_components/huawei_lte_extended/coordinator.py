"""DataUpdateCoordinator for Huawei LTE Extended SMS polling."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from huawei_lte_api.enums.sms import BoxTypeEnum, SortTypeEnum

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_PARENT_ENTRY_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SMS_PAGE_SIZE,
    DOMAIN,
    EVENT_SMS_RECEIVED,
    HUAWEI_LTE_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _parse_sms_list(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse get_sms_list response into a list of message dicts."""
    messages_container = response.get("Messages")
    if not messages_container:
        return []

    messages_raw = messages_container.get("Message", [])
    # API returns dict instead of list when there is exactly one message
    if isinstance(messages_raw, dict):
        messages_raw = [messages_raw]

    messages = []
    for msg in messages_raw:
        messages.append(
            {
                "index": int(msg.get("Index", 0)),
                "phone": msg.get("Phone", ""),
                "content": msg.get("Content", ""),
                "date": msg.get("Date", ""),
                "read": int(msg.get("Smstat", 0)) == 1,
                "sms_type": int(msg.get("SmsType", 0)),
            }
        )
    return messages


class HuaweiLteSmsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for polling SMS from Huawei LTE router."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self._parent_entry_id: str = entry.data[CONF_PARENT_ENTRY_ID]
        scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self._known_indices: set[int] = set()
        self._initial_scan_done: bool = False
        self._api_lock = asyncio.Lock()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    def _get_router(self) -> Any:
        """Get the parent huawei_lte Router object."""
        huawei_data = self.hass.data.get(HUAWEI_LTE_DOMAIN)
        if huawei_data is None:
            raise ConfigEntryNotReady("huawei_lte integration not loaded")

        router = huawei_data.routers.get(self._parent_entry_id)
        if router is None:
            raise UpdateFailed(
                f"Parent router {self._parent_entry_id} not found. "
                "Is the Huawei LTE integration loaded?"
            )
        return router

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch SMS list from router."""
        router = self._get_router()

        if router.suspended:
            raise UpdateFailed("Router is suspended")

        async with self._api_lock:
            try:
                response = await self.hass.async_add_executor_job(
                    router.client.sms.get_sms_list,
                    1,  # page
                    BoxTypeEnum.LOCAL_INBOX,
                    DEFAULT_SMS_PAGE_SIZE,
                    SortTypeEnum.DATE,
                    False,  # ascending
                    True,  # unread_preferred
                )
            except Exception as err:
                raise UpdateFailed(f"Error fetching SMS list: {err}") from err

        messages = _parse_sms_list(response)
        current_indices = {msg["index"] for msg in messages}

        # Fire events for new messages (skip first scan to avoid flooding)
        if self._initial_scan_done:
            new_indices = current_indices - self._known_indices
            for msg in messages:
                if msg["index"] in new_indices:
                    _LOGGER.debug(
                        "New SMS from %s: %s", msg["phone"], msg["content"][:50]
                    )
                    self.hass.bus.async_fire(
                        EVENT_SMS_RECEIVED,
                        {
                            "entry_id": self.config_entry.entry_id,
                            "phone": msg["phone"],
                            "content": msg["content"],
                            "date": msg["date"],
                            "index": msg["index"],
                        },
                    )
        else:
            self._initial_scan_done = True

        self._known_indices = current_indices

        unread_count = sum(1 for msg in messages if not msg["read"])
        total_count = int(response.get("Count", len(messages)))

        return {
            "messages": messages,
            "unread_count": unread_count,
            "total_count": total_count,
        }

    async def async_get_sms_list(
        self, page: int = 1, count: int = DEFAULT_SMS_PAGE_SIZE
    ) -> list[dict[str, Any]]:
        """Fetch SMS list on demand (for service call)."""
        router = self._get_router()

        async with self._api_lock:
            response = await self.hass.async_add_executor_job(
                router.client.sms.get_sms_list,
                page,
                BoxTypeEnum.LOCAL_INBOX,
                count,
                SortTypeEnum.DATE,
                False,
                True,
            )

        return _parse_sms_list(response)

    async def async_delete_sms(self, sms_index: int) -> None:
        """Delete an SMS by index."""
        router = self._get_router()

        async with self._api_lock:
            await self.hass.async_add_executor_job(
                router.client.sms.delete_sms, sms_index
            )

        await self.async_request_refresh()

    async def async_mark_read(self, sms_index: int) -> None:
        """Mark an SMS as read."""
        router = self._get_router()

        async with self._api_lock:
            await self.hass.async_add_executor_job(
                router.client.sms.set_read, sms_index
            )

        await self.async_request_refresh()
