"""Unit tests for pure functions: event_to_periods, get_current_period, _to_local_naive."""
from datetime import datetime, time, timezone, timedelta

import pytest

from backend.app.main import event_to_periods, get_current_period, _to_local_naive, PERIODS


# ---------------------------------------------------------------------------
# _to_local_naive
# ---------------------------------------------------------------------------

def test_to_local_naive_strips_tzinfo():
    aware = datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc)
    result = _to_local_naive(aware)
    assert result.tzinfo is None


def test_to_local_naive_passthrough_naive():
    naive = datetime(2026, 4, 11, 10, 0)
    result = _to_local_naive(naive)
    assert result == naive
    assert result.tzinfo is None


def test_to_local_naive_none_returns_none():
    assert _to_local_naive(None) is None


def test_to_local_naive_aware_value_preserved():
    # 12:00 UTC converted to IST (+5:30) should land at 17:30
    aware = datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc)
    result = _to_local_naive(aware)
    local_tz = datetime.now().astimezone().tzinfo
    expected = aware.astimezone(local_tz).replace(tzinfo=None)
    assert result == expected


# ---------------------------------------------------------------------------
# event_to_periods
# ---------------------------------------------------------------------------

def test_event_single_period_overlap():
    s = datetime(2026, 4, 11, 10, 15)
    e = datetime(2026, 4, 11, 10, 45)
    result = event_to_periods(s, e)
    assert len(result) == 1
    assert result[0]["period_index"] == 1


def test_event_spans_two_periods():
    s = datetime(2026, 4, 11, 10, 30)
    e = datetime(2026, 4, 11, 11, 30)
    result = event_to_periods(s, e)
    indices = [r["period_index"] for r in result]
    assert 1 in indices
    assert 2 in indices


def test_event_spans_all_six_periods():
    s = datetime(2026, 4, 11, 10, 0)
    e = datetime(2026, 4, 11, 16, 40)
    result = event_to_periods(s, e)
    indices = {r["period_index"] for r in result}
    assert indices == {1, 2, 3, 4, 5, 6}


def test_event_outside_all_periods_returns_empty():
    s = datetime(2026, 4, 11, 5, 0)
    e = datetime(2026, 4, 11, 8, 0)
    assert event_to_periods(s, e) == []


def test_event_after_last_period_returns_empty():
    s = datetime(2026, 4, 11, 17, 0)
    e = datetime(2026, 4, 11, 18, 0)
    assert event_to_periods(s, e) == []


def test_event_only_in_lunch_gap_returns_empty():
    # 13:00–13:40 is not a college period
    s = datetime(2026, 4, 11, 13, 5)
    e = datetime(2026, 4, 11, 13, 35)
    assert event_to_periods(s, e) == []


def test_event_spans_lunch_captures_both_sides():
    # 12:30 to 14:10 spans period 3 (12-13), lunch, period 4 (13:40-14:40)
    s = datetime(2026, 4, 11, 12, 30)
    e = datetime(2026, 4, 11, 14, 10)
    indices = {r["period_index"] for r in event_to_periods(s, e)}
    assert 3 in indices
    assert 4 in indices


def test_event_exact_period_boundary_inclusive():
    # Exactly period 1 window: 10:00–11:00
    s = datetime(2026, 4, 11, 10, 0)
    e = datetime(2026, 4, 11, 11, 0)
    result = event_to_periods(s, e)
    assert any(r["period_index"] == 1 for r in result)


def test_event_start_equals_end_period_boundary_exclusive():
    # start=end=10:00 → zero-length; start >= end check is in create_letter, not here
    # event_to_periods with start==end: start < p_end AND end > p_start
    # 10:00 < 11:00 is True, but 10:00 > 10:00 is False → no overlap
    s = e = datetime(2026, 4, 11, 10, 0)
    result = event_to_periods(s, e)
    assert result == []


def test_event_multi_day_captures_each_day():
    s = datetime(2026, 4, 11, 10, 30)
    e = datetime(2026, 4, 13, 10, 30)
    dates = {r["date"] for r in event_to_periods(s, e)}
    assert "2026-04-11" in dates
    assert "2026-04-12" in dates
    assert "2026-04-13" in dates


def test_event_to_periods_correct_date_in_result():
    s = datetime(2026, 6, 15, 10, 30)
    e = datetime(2026, 6, 15, 10, 45)
    result = event_to_periods(s, e)
    assert result[0]["date"] == "2026-06-15"


# ---------------------------------------------------------------------------
# get_current_period
# ---------------------------------------------------------------------------

def test_get_current_period_period_1():
    dt = datetime(2026, 4, 20, 10, 30)  # Monday 10:30
    day, p = get_current_period(dt)
    assert day == "Monday"
    assert p == 1


def test_get_current_period_period_3():
    dt = datetime(2026, 4, 20, 12, 30)  # Monday 12:30
    _, p = get_current_period(dt)
    assert p == 3


def test_get_current_period_period_4():
    dt = datetime(2026, 4, 20, 14, 0)  # Monday 14:00
    _, p = get_current_period(dt)
    assert p == 4


def test_get_current_period_period_6():
    dt = datetime(2026, 4, 20, 16, 0)  # Monday 16:00
    _, p = get_current_period(dt)
    assert p == 6


def test_get_current_period_before_all_returns_period_1():
    dt = datetime(2026, 4, 20, 8, 0)
    _, p = get_current_period(dt)
    assert p == PERIODS[0][0]


def test_get_current_period_after_all_returns_last():
    dt = datetime(2026, 4, 20, 18, 0)
    _, p = get_current_period(dt)
    assert p == PERIODS[-1][0]


def test_get_current_period_during_lunch_returns_next_period():
    # During lunch gap (13:00–13:40), next upcoming period is period 4 (starts 13:40)
    dt = datetime(2026, 4, 20, 13, 10)
    _, p = get_current_period(dt)
    assert p == 4


def test_get_current_period_late_in_lunch_still_returns_period_4():
    dt = datetime(2026, 4, 20, 13, 39)
    _, p = get_current_period(dt)
    assert p == 4


def test_get_current_period_day_of_week_correct():
    dt = datetime(2026, 4, 21, 10, 30)  # Tuesday
    day, _ = get_current_period(dt)
    assert day == "Tuesday"


def test_get_current_period_defaults_to_now(monkeypatch):
    # Without passing dt, uses datetime.now() — just verify it returns a (str, int) tuple
    day, p = get_current_period()
    assert isinstance(day, str)
    assert isinstance(p, int)
