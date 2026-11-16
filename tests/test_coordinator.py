"""Exercise coordinator I/O with small Home Assistant interface doubles."""

from enum import IntEnum
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / "custom_components/huawei_lte_extended"


class CoordinatorBase:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, logger, **kwargs):
        self.hass = hass


class UpdateFailed(Exception):
    pass


class BoxType(IntEnum):
    LOCAL_INBOX = 1


class SortType(IntEnum):
    DATE = 0


def load_coordinator():
    """Load production code without executing integration setup imports."""
    attributes = {
        "huawei_lte_api.enums.sms": dict(BoxTypeEnum=BoxType, SortTypeEnum=SortType),
        "homeassistant.config_entries": dict(ConfigEntry=object),
        "homeassistant.core": dict(HomeAssistant=object),
        "homeassistant.exceptions": dict(ConfigEntryNotReady=RuntimeError),
        "homeassistant.helpers.update_coordinator": dict(
            DataUpdateCoordinator=CoordinatorBase, UpdateFailed=UpdateFailed),
        "sms_test_package": dict(__path__=[str(SOURCE)]),
    }
    modules = {}
    for name, values in attributes.items():
        module = ModuleType(name)
        module.__dict__.update(values)
        modules[name] = module
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location(
            "sms_test_package.coordinator", SOURCE / "coordinator.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def raw(index, content=None):
    return dict(Index=str(index), Phone="10000", Content=content or str(index),
                Date="2026-11-16 13:55:19", Smstat="0", SmsType="1")


def response(messages):
    return dict(Count=str(len(messages)), Messages=dict(Message=messages))


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = load_coordinator()
        self.client = Mock()
        router = SimpleNamespace(suspended=False, client=SimpleNamespace(sms=self.client))
        parent = SimpleNamespace(domain="huawei_lte", runtime_data=router)

        async def executor(function, *args):
            return function(*args)

        self.hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_get_entry=lambda entry_id: parent),
            async_add_executor_job=executor, bus=SimpleNamespace(async_fire=Mock()))
        entry = SimpleNamespace(data=dict(parent_entry_id="parent", scan_interval=20),
                                entry_id="sms-entry")
        self.coordinator = self.module.HuaweiLteSmsCoordinator(self.hass, entry)
        self.coordinator.config_entry = entry

    async def test_reads_all_pages_and_baselines_history(self):
        self.client.get_sms_list.side_effect = [
            response([raw(i) for i in range(20)]), response([raw(20)])]
        result = await self.coordinator._async_update_data()
        self.assertEqual(len(result["messages"]), 21)
        self.assertEqual(result["total_count"], 21)
        self.assertEqual([c.args[0] for c in self.client.get_sms_list.call_args_list], [1, 2])
        self.assertTrue(all(c.args[-1] is False
                            for c in self.client.get_sms_list.call_args_list))
        self.hass.bus.async_fire.assert_not_called()

    async def test_recycled_index_emits_compatible_event_after_confirmation(self):
        old, new = raw(40035, "Old"), raw(40034, "New")
        self.client.get_sms_list.side_effect = [response([old]),
                                               response([new, old]), response([new, old])]
        with patch.object(self.module, "monotonic", side_effect=[0, 20, 40]):
            await self.coordinator._async_update_data()
            await self.coordinator._async_update_data()
            self.hass.bus.async_fire.assert_not_called()
            await self.coordinator._async_update_data()
        self.hass.bus.async_fire.assert_called_once_with(
            "huawei_lte_extended_sms_received",
            dict(entry_id="sms-entry", phone="10000", content="New",
                 date=new["Date"], index=40034))

    async def test_partial_failed_scan_does_not_initialize_tracker(self):
        self.client.get_sms_list.side_effect = [
            response([raw(i) for i in range(20)]), OSError("Example failure"),
            response([raw(0)])]
        with self.assertRaises(UpdateFailed):
            await self.coordinator._async_update_data()
        await self.coordinator._async_update_data()
        self.hass.bus.async_fire.assert_not_called()

    async def test_repeated_page_is_rejected_without_looping(self):
        self.client.get_sms_list.return_value = response([raw(i) for i in range(20)])
        with self.assertRaises(UpdateFailed):
            await self.coordinator._async_update_data()
        self.assertEqual(self.client.get_sms_list.call_count, 2)
        self.hass.bus.async_fire.assert_not_called()

    def test_single_message_response(self):
        self.assertEqual(self.module._parse_sms_list(response(raw(4)))[0]["index"], 4)


if __name__ == "__main__":
    unittest.main()
