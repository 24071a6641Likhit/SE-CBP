"""System-level E2E tests covering full role workflows."""
from datetime import datetime as _RealDatetime
from unittest.mock import patch

import pytest

from backend.tests.conftest import auth_hdr
from backend.app.database import SessionLocal
from backend.app import models

_MONDAY_P1 = _RealDatetime(2026, 4, 20, 10, 30)
_MONDAY_P1_DATE = "2026-04-20"


class _MockDatetime(_RealDatetime):
    @classmethod
    def now(cls, tz=None):
        return _MONDAY_P1

    @classmethod
    def utcnow(cls):
        return _MONDAY_P1


# ---------------------------------------------------------------------------
# Full chain: Student → Coordinator → Teacher
# ---------------------------------------------------------------------------

def test_full_student_coordinator_teacher_chain(client, student_token, coordinator_token,
                                                 teacher_token, timetable_monday_p1):
    """
    1. Student submits letter for an event during period 1.
    2. Coordinator approves — attendance created as Present.
    3. Teacher fetches attendance and sees the student as Present.
    4. Teacher marks same student Absent (override) in current period.
    5. Audit log reflects all actions.
    """
    # Step 1: student submits letter
    r = client.post("/api/letters", json={
        "student_roll": "TST001",
        "student_name": "Student One",
        "event_name": "InterCollegeHackathon",
        "start_datetime": f"{_MONDAY_P1_DATE}T10:00:00",
        "end_datetime": f"{_MONDAY_P1_DATE}T11:00:00",
    }, headers=auth_hdr(student_token))
    assert r.status_code == 201, r.text
    letter_id = r.json()["id"]
    assert r.json()["status"] == "Submitted"

    # Step 2: coordinator sees the letter
    letters = client.get("/api/letters?status=Submitted", headers=auth_hdr(coordinator_token))
    assert any(l["id"] == letter_id for l in letters.json())

    # Step 3: coordinator approves
    approve = client.post(f"/api/letters/{letter_id}/approve", headers=auth_hdr(coordinator_token))
    assert approve.status_code == 200
    affected = approve.json()["affected_periods"]
    assert len(affected) >= 1

    # Step 4: attendance shows Present for TST001
    att = client.get("/api/attendance",
                     params={"date": _MONDAY_P1_DATE, "period": 1},
                     headers=auth_hdr(coordinator_token))
    assert att.status_code == 200
    tst001_row = next((row for row in att.json() if row["student_roll"] == "TST001"), None)
    assert tst001_row is not None
    assert tst001_row["mark"] == "Present"
    assert tst001_row["source"] == "SystemAuto"

    # Step 5: teacher can override the mark (mocked to Monday period 1)
    with patch("backend.app.main.datetime", _MockDatetime):
        r = client.post("/api/attendance", json={"updates": [{
            "student_roll": "TST001",
            "date": _MONDAY_P1_DATE,
            "period_index": 1,
            "mark": "Absent",
        }]}, headers=auth_hdr(teacher_token))
    assert r.status_code == 200

    # Step 6: verify override
    att2 = client.get("/api/attendance",
                      params={"date": _MONDAY_P1_DATE, "period": 1},
                      headers=auth_hdr(coordinator_token))
    tst001_row2 = next((row for row in att2.json() if row["student_roll"] == "TST001"), None)
    assert tst001_row2["mark"] == "Absent"
    assert tst001_row2["source"] == "Manual"

    # Step 7: audit log has letter.approve and attendance.update entries
    audit = client.get("/api/audit", headers=auth_hdr(coordinator_token))
    assert audit.status_code == 200
    actions = {a["action"] for a in audit.json()}
    assert "letter.approve" in actions
    assert "attendance.update" in actions or "attendance.create" in actions


# ---------------------------------------------------------------------------
# Rejection flow
# ---------------------------------------------------------------------------

def test_rejection_flow_no_attendance_side_effect(client, student_token, coordinator_token):
    """Rejected letter must not create any attendance records."""
    r = client.post("/api/letters", json={
        "student_roll": "TST002",
        "student_name": "Student Two",
        "event_name": "RejectionFlowTest",
        "start_datetime": "2025-12-10T10:00:00",
        "end_datetime": "2025-12-10T12:00:00",
    }, headers=auth_hdr(student_token))
    assert r.status_code == 201
    letter_id = r.json()["id"]

    reject = client.post(f"/api/letters/{letter_id}/reject",
                         json={"comment": "Not a recognised event"},
                         headers=auth_hdr(coordinator_token))
    assert reject.status_code == 200

    att = client.get("/api/attendance",
                     params={"date": "2025-12-10", "period": 1},
                     headers=auth_hdr(coordinator_token))
    tst002_row = next((row for row in att.json() if row["student_roll"] == "TST002"), None)
    assert tst002_row is None or tst002_row["mark"] == "Absent"

    detail = client.get(f"/api/letters/{letter_id}", headers=auth_hdr(coordinator_token))
    assert detail.json()["status"] == "Rejected"
    assert detail.json()["coordinator_comment"] == "Not a recognised event"


# ---------------------------------------------------------------------------
# Multi-student, multi-period event
# ---------------------------------------------------------------------------

def test_multi_period_approval_creates_all_records(client, coordinator_token):
    """Approving a long event should create attendance for every affected period."""
    r = client.post("/api/letters", json={
        "student_roll": "TST003",
        "student_name": "Student Three",
        "event_name": "FullDayEvent",
        "start_datetime": "2025-12-15T10:00:00",
        "end_datetime": "2025-12-15T16:40:00",
    }, headers=auth_hdr(coordinator_token))
    assert r.status_code == 201
    letter_id = r.json()["id"]

    approve = client.post(f"/api/letters/{letter_id}/approve", headers=auth_hdr(coordinator_token))
    assert approve.status_code == 200
    periods = approve.json()["affected_periods"]
    period_indices = {p["period_index"] for p in periods}
    assert period_indices == {1, 2, 3, 4, 5, 6}

    for p in periods:
        att = client.get("/api/attendance",
                         params={"date": p["date"], "period": p["period_index"]},
                         headers=auth_hdr(coordinator_token))
        row = next((r for r in att.json() if r["student_roll"] == "TST003"), None)
        assert row and row["mark"] == "Present", f"Period {p['period_index']} not Present"


# ---------------------------------------------------------------------------
# Audit log access control
# ---------------------------------------------------------------------------

def test_coordinator_can_read_audit(client, coordinator_token):
    r = client.get("/api/audit", headers=auth_hdr(coordinator_token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_maintainer_can_read_audit(client, maintainer_token):
    r = client.get("/api/audit", headers=auth_hdr(maintainer_token))
    assert r.status_code == 200


def test_student_cannot_read_audit(client, student_token):
    r = client.get("/api/audit", headers=auth_hdr(student_token))
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# current_period endpoint
# ---------------------------------------------------------------------------

def test_current_period_no_timetable(client, teacher_token):
    r = client.get("/api/current_period", headers=auth_hdr(teacher_token))
    assert r.status_code == 200
    body = r.json()
    assert "day" in body
    assert "period" in body


def test_current_period_with_timetable(client, teacher_token, timetable_monday_p1):
    with patch("backend.app.main.datetime", _MockDatetime):
        r = client.get("/api/current_period", headers=auth_hdr(teacher_token))
    assert r.status_code == 200
    body = r.json()
    assert body["day"] == "Monday"
    assert body["period"] == 1
    assert body["subject"]["code"] == "TSUB"
    assert body["teacher_name"] == "Test Teacher"
    assert body["assigned"] is True
