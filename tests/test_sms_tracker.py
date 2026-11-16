"""Offline regression tests; no Home Assistant installation is required."""

import importlib.util
from pathlib import Path
import sys
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "custom_components/huawei_lte_extended"
SPEC = importlib.util.spec_from_file_location("sms_tracker", SOURCE / "sms_tracker.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
SmsTracker = MODULE.SmsTracker


def sms(index=40034, content="Example message", date="2026-11-16 13:55:19", **kwargs):
    return dict(index=index, phone="10000", content=content, date=date,
                read=False, sms_type=1) | kwargs


class SmsTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tracker = SmsTracker(20)
        self.old = sms(40035, "Earlier message", "2026-11-16 11:45:45")
        self.assertEqual(self.tracker.update([self.old], 0), [])

    def test_lower_reused_index_is_announced_once_after_settling(self):
        new = sms()
        self.assertEqual(self.tracker.update([new, self.old], 20), [])
        self.assertEqual(self.tracker.update([new, self.old], 40), [new])
        self.assertEqual(self.tracker.update([new, self.old], 60), [])

    def test_empty_baseline_and_empty_inbox(self):
        tracker = SmsTracker(20)
        self.assertEqual(tracker.update([], 0), [])
        self.assertEqual(tracker.update([sms()], 20), [])
        self.assertEqual(tracker.update([sms()], 40), [sms()])
        self.assertEqual(tracker.update([], 60), [])

    def test_first_scan_does_not_announce_history(self):
        self.assertEqual(self.tracker.update([self.old], 100), [])

    def test_reindex_and_read_changes_do_not_repeat_notifications(self):
        moved = self.old | dict(index=1, read=True)
        self.assertEqual(self.tracker.update([moved], 20), [])
        self.assertEqual(self.tracker.update([moved], 40), [])

    def test_latest_index_is_used_in_event(self):
        self.tracker.update([sms()], 20)
        moved = sms(index=4, read=True)
        self.assertEqual(self.tracker.update([moved], 40), [moved])

    def test_identical_text_at_different_times_is_a_new_sms(self):
        new = self.old | dict(date="2026-11-16 12:00:00")
        self.tracker.update([new, self.old], 20)
        self.assertEqual(self.tracker.update([new, self.old], 40), [new])

    def test_same_slot_and_timestamp_with_changed_body_is_detected(self):
        new = self.old | dict(content="Different message")
        self.tracker.update([new], 20)
        self.assertEqual(self.tracker.update([new], 40), [new])

    def test_several_arrivals_are_each_announced(self):
        new = [sms(index=i, content=str(i)) for i in range(3)]
        self.tracker.update(new, 20)
        self.assertEqual(self.tracker.update(new, 40), new)

    def test_repeated_refresh_does_not_bypass_settling(self):
        self.tracker.update([sms()], 20)
        self.assertEqual(self.tracker.update([sms()], 20.1), [])
        self.assertEqual(self.tracker.update([sms()], 39.9), [])
        self.assertEqual(self.tracker.update([sms()], 40), [sms()])

    def test_deleted_pending_message_is_not_announced(self):
        self.tracker.update([sms()], 20)
        self.assertEqual(self.tracker.update([], 40), [])
        self.assertEqual(self.tracker.update([sms()], 60), [])

    def test_fragment_replaced_by_full_body_under_another_index(self):
        part = sms(content="middle", sms_type=2)
        whole = sms(index=40036, content="start middle end", sms_type=2)
        self.tracker.update([part, self.old], 20)
        self.assertEqual(self.tracker.update([whole, self.old], 40), [])
        self.assertEqual(self.tracker.update([whole, self.old], 60), [whole])
        self.assertEqual(self.tracker.update([whole, self.old], 80), [])

    def test_coexisting_fragments_are_suppressed(self):
        part = sms(content="middle", sms_type=2)
        whole = sms(index=40036, content="start middle end", sms_type=2)
        self.tracker.update([part, whole], 20)
        self.assertEqual(self.tracker.update([part, whole], 40), [whole])

    def test_independent_messages_from_same_sender_and_time_are_kept(self):
        new = [sms(content="abc"), sms(index=2, content="xyz")]
        self.tracker.update(new, 20)
        self.assertEqual(self.tracker.update(new, 40), new)

    def test_substrings_are_not_collapsed_for_single_part_messages(self):
        new = [sms(content="abc"), sms(index=2, content="abcdef")]
        self.tracker.update(new, 20)
        self.assertEqual(self.tracker.update(new, 40), new)

    def test_rebuilding_cannot_postpone_arrival_forever(self):
        self.tracker.update([sms(content="a", sms_type=2)], 20)
        self.assertEqual(self.tracker.update([sms(content="ab", sms_type=2)], 40), [])
        self.assertEqual(self.tracker.update([sms(content="abc", sms_type=2)], 60), [])
        whole = sms(content="abcd", sms_type=2)
        self.assertEqual(self.tracker.update([whole], 80), [whole])

    def test_failed_polls_do_not_clear_pending_messages(self):
        self.tracker.update([sms()], 20)
        # A failed scan never calls update; the next successful one confirms it.
        self.assertEqual(self.tracker.update([sms()], 200), [sms()])

    def test_default_sixty_second_poll_waits_for_confirmation(self):
        tracker = SmsTracker(60)
        tracker.update([], 0)
        self.assertEqual(tracker.update([sms()], 60), [])
        self.assertEqual(tracker.update([sms()], 120), [sms()])

    def test_large_initial_inbox_is_not_evicted_and_reannounced(self):
        tracker = SmsTracker(20)
        messages = [sms(index=i, content=str(i)) for i in range(2100)]
        tracker.update(messages, 0)
        self.assertEqual(tracker.update(messages, 20), [])
        self.assertEqual(tracker.update(messages, 40), [])

    def test_removed_history_is_bounded(self):
        for i in range(2200):
            message = sms(content=str(i))
            self.tracker.update([message], 20 + i * 40)
            self.tracker.update([message], 40 + i * 40)
        self.assertLessEqual(len(self.tracker._seen), 2049)

    def test_mass_removal_does_not_evict_a_remaining_message(self):
        tracker = SmsTracker(20)
        messages = [sms(index=i, content=str(i)) for i in range(2100)]
        tracker.update([], 0)
        tracker.update(messages, 20)
        remaining = messages[:1]
        self.assertEqual(tracker.update(remaining, 40), remaining)
        self.assertEqual(tracker.update(remaining, 60), [])
        self.assertLessEqual(len(tracker._seen), 2049)


if __name__ == "__main__":
    unittest.main()
