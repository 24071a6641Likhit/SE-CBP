"""Attendance tests: GET, POST (teacher enforcement, version conflict, coordinator access)."""
from datetime import datetime as _RealDatetime
from unittest.mock import patch

import pytest

from backend.tests.conftest import auth_hdr

# April 20, 2026 is a Monday — confirmed by strftime('%A')
_MONDAY_P1 = _RealDatetime(2026, 4, 20, 10, 30)
_MONDAY_P1_DATE = "2026-04-20"


class _MockDatetime(_RealDatetime):
    """Subclass that freezes now() and utcnow() to _MONDAY_P1."""
    @classmethod
    def now(cls, tz=None):
        return _MONDAY_P1

    @classmethod
    def utcnow(cls):
        return _MONDAY_P1


# ---------------------------------------------------------------------------
# GET /api/attendance
# ---------------------------------------------------------------------------

def test_get_attendance_returns_all_students(client, coordinator_token):
    r = client.get("/api/attendance", params={"date": "2024-01-01", "period": 1},
                   headers=auth_hdr(coordinator_token))
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    rolls = [row["student_roll"] for row in rows]
    assert "TST001" in rolls
    assert "TST002" in rolls
    assert "TST003" in rolls


def test_get_attendance_default_absent_when_no_record(client, coordinator_token):
    r = client.get("/api/attendance", params={"date": "2024-01-02", "period": 2},
                   headers=auth_hdr(coordinator_token))
    rows = r.json()
    for row in rows:
        assert row["mark"] == "Absent"
        assert row["source"] == "Manual"


def test_get_attendance_shows_present_after_approval(client, student_token, coordinator_token):
    # Submit + approve a letter for a unique date
    r = client.post("/api/letters", json={
        "student_roll": "TST002",
        "student_name": "Student Two",
        "event_name": "AttendCheckEvent",
        "start_datetime": "2024-02-01T10:30:00",
        "end_datetime": "2024-02-01T11:30:00",
    }, headers=auth_hdr(coordinator_token))
    assert r.status_code == 201
    letter_id = r.json()["id"]

    approve = client.post(f"/api/letters/{letter_id}/approve", headers=auth_hdr(coordinator_token))
    assert approve.status_code == 200

    r = client.get("/api/attendance", params={"date": "2024-02-01", "period": 1},
                   headers=auth_hdr(coordinator_token))
    found = [row for row in r.json() if row["student_roll"] == "TST002"]
    assert found and found[0]["mark"] == "Present"


def test_get_attendance_invalid_date(client, coordinator_token):
    r = client.get("/api/attendance", params={"date": "not-a-date", "period": 1},
                   headers=auth_hdr(coordinator_token))
    assert r.status_code == 400


def test_get_attendance_requires_auth(client):
    r = client.get("/api/attendance", params={"date": "2024-01-01", "period": 1})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/attendance — coordinator (no restrictions)
# ---------------------------------------------------------------------------

def test_coordinator_can_save_any_period(client, coordinator_token):
    payload = {"updates": [{
        "student_roll": "TST001",
        "date": "2024-03-01",
        "period_index": 3,
        "mark": "Absent",
    }]}
    r = client.post("/api/attendance", json=payload, headers=auth_hdr(coordinator_token))
    assert r.status_code == 200
    assert r.json()["updated"] == 1


def test_coordinator_can_save_past_date(client, coordinator_token):
    payload = {"updates": [{
        "student_roll": "TST002",
        "date": "2020-01-15",
        "period_index": 1,
        "mark": "Absent",
    }]}
    r = client.post("/api/attendance", json=payload, headers=auth_hdr(coordinator_token))
    assert r.status_code == 200


def test_attendance_update_overwrites_existing(client, coordinator_token):
    update = lambda mark: client.post("/api/attendance", json={"updates": [{
        "student_roll": "TST003",
        "date": "2024-03-05",
        "period_index": 2,
        "mark": mark,
    }]}, headers=auth_hdr(coordinator_token))
    r1 = update("Absent")
    assert r1.status_code == 200
    r2 = update("Present")
    assert r2.status_code == 200
    assert r2.json().get("warnings")  # second update should warn "already provided"

    r = client.get("/api/attendance", params={"date": "2024-03-05", "period": 2},
                   headers=auth_hdr(coordinator_token))
    found = [row for row in r.json() if row["student_roll"] == "TST003"]
    assert found[0]["mark"] == "Present"


def test_version_conflict_returns_409(client, coordinator_token):
    # First save creates version=1
    client.post("/api/attendance", json={"updates": [{
        "student_roll": "TST001",
        "date": "2024-04-01",
        "period_index": 1,
        "mark": "Absent",
    }]}, headers=auth_hdr(coordinator_token))

    # Try to update with wrong version
    r = client.post("/api/attendance", json={"updates": [{
        "student_roll": "TST001",
        "date": "2024-04-01",
        "period_index": 1,
        "mark": "Present",
        "version": 99,
    }]}, headers=auth_hdr(coordinator_token))
    assert r.status_code == 409


def test_attendance_save_empty_updates_returns_zero(client, coordinator_token):
    r = client.post("/api/attendance", json={"updates": []}, headers=auth_hdr(coordinator_token))
    assert r.status_code == 200
    assert r.json()["updated"] == 0


def test_attendance_invalid_payload(client, coordinator_token):
    r = client.post("/api/attendance", json={"updates": "not-a-list"}, headers=auth_hdr(coordinator_token))
    assert r.status_code == 400


def test_attendance_pindex_zero_not_silently_skipped(client, coordinator_token):
    # period_index=0 (lunch slot) must NOT be silently dropped by falsy check
    # The update should either be saved or return an explicit error — never silently ignored
    payload = {"updates": [{
        "student_roll": "TST001",
        "date": "2024-05-01",
        "period_index": 0,
        "mark": "Absent",
    }]}
    r = client.post("/api/attendance", json=payload, headers=auth_hdr(coordinator_token))
    assert r.status_code == 200
    assert r.json()["updated"] == 1  # should be saved, not silently dropped


def test_attendance_missing_required_fields_skipped(client, coordinator_token):
    # Update missing student_roll — should be skipped, not crash
    payload = {"updates": [{"date": "2024-05-02", "period_index": 1, "mark": "Present"}]}
    r = client.post("/api/attendance", json=payload, headers=auth_hdr(coordinator_token))
    assert r.status_code == 200
    assert r.json()["updated"] == 0


# ---------------------------------------------------------------------------
# POST /api/attendance — teacher enforcement
# ---------------------------------------------------------------------------

def test_teacher_can_save_current_period(client, teacher_token, timetable_monday_p1):
    payload = {"updates": [{
        "student_roll": "TST001",
        "date": _MONDAY_P1_DATE,
        "period_index": 1,
        "mark": "Present",
    }]}
    with patch("backend.app.main.datetime", _MockDatetime):
        r = client.post("/api/attendance", json=payload, headers=auth_hdr(teacher_token))
    assert r.status_code == 200
    assert r.json()["updated"] == 1


def test_teacher_save_wrong_date_forbidden(client, teacher_token, timetable_monday_p1):
    payload = {"updates": [{
        "student_roll": "TST001",
        "date": "2020-01-01",
        "period_index": 1,
        "mark": "Present",
    }]}
    with patch("backend.app.main.datetime", _MockDatetime):
        r = client.post("/api/attendance", json=payload, headers=auth_hdr(teacher_token))
    assert r.status_code == 403
    assert "Unauthorized period access" in r.text


def test_teacher_save_wrong_period_forbidden(client, teacher_token, timetable_monday_p1):
    payload = {"updates": [{
        "student_roll": "TST001",
        "date": _MONDAY_P1_DATE,
        "period_index": 3,  # current is 1
        "mark": "Present",
    }]}
    with patch("backend.app.main.datetime", _MockDatetime):
        r = client.post("/api/attendance", json=payload, headers=auth_hdr(teacher_token))
    assert r.status_code == 403


def test_teacher_save_not_assigned_subject_forbidden(client, teacher2_token, timetable_monday_p1):
    # teacher2 is not assigned to TSUB
    payload = {"updates": [{
        "student_roll": "TST001",
        "date": _MONDAY_P1_DATE,
        "period_index": 1,
        "mark": "Present",
    }]}
    with patch("backend.app.main.datetime", _MockDatetime):
        r = client.post("/api/attendance", json=payload, headers=auth_hdr(teacher2_token))
    assert r.status_code == 403
    assert "not the assigned teacher" in r.text


def test_teacher_save_no_timetable_entry_forbidden(client, teacher_token):
    # No timetable_monday_p1 fixture → no TSUB entry for Monday/period1
    payload = {"updates": [{
        "student_roll": "TST001",
        "date": _MONDAY_P1_DATE,
        "period_index": 1,
        "mark": "Present",
    }]}
    with patch("backend.app.main.datetime", _MockDatetime):
        r = client.post("/api/attendance", json=payload, headers=auth_hdr(teacher_token))
    assert r.status_code == 403


def test_teacher_save_audit_log_created(client, teacher_token, coordinator_token, timetable_monday_p1):
    payload = {"updates": [{
        "student_roll": "TST002",
        "date": _MONDAY_P1_DATE,
        "period_index": 1,
        "mark": "Absent",
    }]}
    with patch("backend.app.main.datetime", _MockDatetime):
        r = client.post("/api/attendance", json=payload, headers=auth_hdr(teacher_token))
    assert r.status_code == 200

    audit = client.get("/api/audit", headers=auth_hdr(coordinator_token))
    actions = [a["action"] for a in audit.json()]
    assert any("attendance" in a for a in actions)
