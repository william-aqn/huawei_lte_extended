"""Constants for Huawei LTE Extended integration."""

from typing import Final

DOMAIN: Final = "huawei_lte_extended"

HUAWEI_LTE_DOMAIN: Final = "huawei_lte"

CONF_PARENT_ENTRY_ID: Final = "parent_entry_id"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 60  # seconds

EVENT_SMS_RECEIVED: Final = "huawei_lte_extended_sms_received"

DEFAULT_SMS_PAGE_SIZE: Final = 20
