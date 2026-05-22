"""Tests for app.utils.account_lockout."""

from __future__ import annotations

import time

import pytest

from app.utils.account_lockout import AccountLockoutTracker, _InMemoryStore


@pytest.fixture
def tracker() -> AccountLockoutTracker:
    return AccountLockoutTracker(
        store=_InMemoryStore(),
        max_fails=5,
        window_sec=900,
        lock_duration_sec=1800,
    )


class TestLockout:
    def test_initial_state_unlocked(self, tracker: AccountLockoutTracker) -> None:
        status = tracker.check("alice@example.com", "1.2.3.4")
        assert status.locked is False
        assert status.failed_count == 0

    def test_locks_after_max_fails(self, tracker: AccountLockoutTracker) -> None:
        for _ in range(4):
            s = tracker.record_failure("alice@example.com", "1.2.3.4")
            assert s.locked is False
        s = tracker.record_failure("alice@example.com", "1.2.3.4")
        assert s.locked is True
        assert s.retry_after_seconds == 1800

    def test_check_after_lock_reports_retry_after(self, tracker: AccountLockoutTracker) -> None:
        for _ in range(5):
            tracker.record_failure("a@b.com", "1.1.1.1")
        status = tracker.check("a@b.com", "1.1.1.1")
        assert status.locked is True
        assert 0 < status.retry_after_seconds <= 1800

    def test_different_ip_for_same_email_not_locked(self, tracker: AccountLockoutTracker) -> None:
        for _ in range(5):
            tracker.record_failure("victim@example.com", "9.9.9.9")
        assert tracker.check("victim@example.com", "9.9.9.9").locked is True
        # Legitimate user from a different IP is unaffected.
        assert tracker.check("victim@example.com", "10.10.10.10").locked is False

    def test_success_clears_failures(self, tracker: AccountLockoutTracker) -> None:
        for _ in range(3):
            tracker.record_failure("a@b.com", "1.1.1.1")
        tracker.record_success("a@b.com", "1.1.1.1")
        assert tracker.check("a@b.com", "1.1.1.1").failed_count == 0

    def test_admin_unlock_clears_lock(self, tracker: AccountLockoutTracker) -> None:
        for _ in range(5):
            tracker.record_failure("a@b.com", "1.1.1.1")
        assert tracker.check("a@b.com", "1.1.1.1").locked is True
        tracker.unlock("a@b.com", "1.1.1.1")
        assert tracker.check("a@b.com", "1.1.1.1").locked is False

    def test_lock_expires(self) -> None:
        t = AccountLockoutTracker(
            store=_InMemoryStore(),
            max_fails=2,
            window_sec=60,
            lock_duration_sec=1,
        )
        t.record_failure("e@x", "ip")
        t.record_failure("e@x", "ip")
        assert t.check("e@x", "ip").locked is True
        # Poll for expiry instead of a fixed sleep — robust to runner jitter
        # when this test runs as part of the full 820-test suite under load.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if not t.check("e@x", "ip").locked:
                return
            time.sleep(0.05)
        raise AssertionError("lock did not expire within 5s of its 1s TTL")
