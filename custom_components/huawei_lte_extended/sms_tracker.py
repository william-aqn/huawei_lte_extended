"""Detect new SMS without assuming router storage indexes increase."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
from typing import Any


def _fingerprint(message: dict[str, Any]) -> str:
    """Ignore mutable storage indexes and read status."""
    identity = [message[name] for name in ("phone", "date", "content")]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()


def _contains(whole: dict[str, Any], part: dict[str, Any]) -> bool:
    """Recognize a fragment contained in a router-assembled multipart SMS."""
    return (
        whole.get("sms_type") == 2
        and bool(whole["phone"] and whole["date"] and part["content"])
        and whole["phone"] == part["phone"]
        and whole["date"] == part["date"]
        and whole["content"] != part["content"]
        and part["content"] in whole["content"]
    )


@dataclass
class _Pending:
    message: dict[str, Any]
    first_seen: float
    stable_since: float


class SmsTracker:
    """Track complete inbox snapshots, using monotonic time for settling."""

    def __init__(self, settle_seconds: float, max_wait_seconds: float = 60) -> None:
        # Scheduled polls have small execution-time differences. Do not require
        # a third poll just because the second finished milliseconds earlier.
        self._settle_seconds = settle_seconds - min(1.0, settle_seconds * 0.05)
        self._max_wait_seconds = max_wait_seconds
        self._initialized = False
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._pending: dict[str, _Pending] = {}

    def update(
        self, messages: list[dict[str, Any]], now: float
    ) -> list[dict[str, Any]]:
        """Return settled arrivals; call only after a successful full scan."""
        current = {_fingerprint(message): message for message in messages}
        if not self._initialized:
            self._initialized = True
            self._seen.update(dict.fromkeys(current))
            return []

        # Keep a short history of removed messages without evicting the inbox.
        for key in current.keys() & self._seen.keys():
            self._seen.move_to_end(key)

        suppressed = {
            key
            for key, part in current.items()
            if any(_contains(whole, part) for whole in messages)
        }
        self._seen.update(dict.fromkeys(suppressed))
        pending: dict[str, _Pending] = {}
        arrivals = []
        for key, message in current.items():
            if key in self._seen:
                continue
            previous = self._pending.get(key)
            if previous is not None:
                item = _Pending(message, previous.first_seen, previous.stable_since)
            else:
                # A merged body can replace fragments under a different index.
                related = [
                    item.first_seen for item in self._pending.values()
                    if _contains(message, item.message)
                ]
                item = _Pending(message, min(related, default=now), now)

            # Even at the deadline, require another successful observation.
            observed_again = previous is not None or item.first_seen < now
            if observed_again and (
                now - item.stable_since >= self._settle_seconds
                or now - item.first_seen >= self._max_wait_seconds
            ):
                arrivals.append(message)
                self._seen[key] = None
            else:
                pending[key] = item

        # Do not announce vanished fragments or messages deleted while settling.
        for key in self._pending.keys() - current.keys():
            self._seen[key] = None
        self._pending = pending
        excess = len(self._seen.keys() - current.keys()) - 2048
        if excess > 0:
            for key in tuple(self._seen):
                if key not in current:
                    del self._seen[key]
                    excess -= 1
                    if excess == 0:
                        break
        return arrivals
