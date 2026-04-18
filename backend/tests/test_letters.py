"""Letter lifecycle tests: create, approve, reject, list, edge cases."""
import pytest
from backend.tests.conftest import auth_hdr


def _submit_letter(client, token, roll="TST001", name="Student One",
                   event="TestEvent", start="2025-06-15T10:30:00", end="2025-06-15T12:30:00"):
    return client.post("/api/letters", json={
        "student_roll": roll,
        "student_name": name,
        "event_name": event,
        "start_datetime": start,
        "end_datetime": end,
    }, headers=auth_hdr(token))


# ---------------------------------------------------------------------------
# Create letter
# ---------------------------------------------------------------------------

def test_create_letter_success(client, student_token):
    r = _submit_letter(client, student_token, event="CreateSuccessEvent")
    assert r.status_code == 201
    body = r.json()
    assert body["student_roll"] == "TST001"
    assert body["status"] == "Submitted"
    assert "id" in body


def test_create_letter_student_not_in_roster(client, student_token):
    r = _submit_letter(client, student_token, roll="NOTEXIST", event="NoRosterEvent")
    assert r.status_code == 400
    assert "Student not found" in r.text


def test_create_letter_event_outside_all_periods(client, student_token):
    r = _submit_letter(client, student_token, event="NightEvent",
                       start="2025-06-15T05:00:00", end="2025-06-15T07:00:00")
    assert r.status_code == 400
    assert "does not overlap" in r.text


def test_create_letter_start_after_end(client, student_token):
    r = _submit_letter(client, student_token, event="BackwardsEvent",
                       start="2025-06-15T12:00:00", end="2025-06-15T10:00:00")
    assert r.status_code == 400


def test_create_letter_start_equals_end(client, student_token):
    r = _submit_letter(client, student_token, event="ZeroDurationEvent",
                       start="2025-06-15T10:00:00", end="2025-06-15T10:00:00")
    assert r.status_code == 400


def test_create_letter_only_in_lunch_gap(client, student_token):
    r = _submit_letter(client, student_token, event="LunchEvent",
                       start="2025-06-15T13:05:00", end="2025-06-15T13:35:00")
    assert r.status_code == 400


def test_create_letter_invalid_datetime_format(client, student_token):
    r = client.post("/api/letters", json={
        "student_roll": "TST001", "student_name": "Student One",
        "event_name": "BadDT", "start_datetime": "not-a-date", "end_datetime": "also-bad",
    }, headers=auth_hdr(student_token))
    assert r.status_code == 400


def test_create_letter_with_body_field(client, student_token):
    r = client.post("/api/letters", json={
        "student_roll": "TST001", "student_name": "Student One",
        "event_name": "WithBody", "body": "Please approve this letter.",
        "start_datetime": "2025-07-01T10:30:00", "end_datetime": "2025-07-01T11:30:00",
    }, headers=auth_hdr(student_token))
    assert r.status_code == 201
    assert r.json()["content"] == "Please approve this letter."


def test_create_letter_no_auth(client):
    r = _submit_letter(client, "invalid_token_here")
    assert r.status_code == 401


def test_duplicate_letter_allowed_no_guard(client, student_token):
    # Current backend has no duplicate letter guard — same student/event can be submitted twice.
    # This test documents the current behavior (not ideal, but real).
    r1 = _submit_letter(client, student_token, event="DuplicateTestEvent",
                        start="2025-08-01T10:30:00", end="2025-08-01T11:30:00")
    r2 = _submit_letter(client, student_token, event="DuplicateTestEvent",
                        start="2025-08-01T10:30:00", end="2025-08-01T11:30:00")
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


# ---------------------------------------------------------------------------
# Approve letter
# ---------------------------------------------------------------------------

def test_approve_letter_success(client, student_token, coordinator_token):
    r = _submit_letter(client, student_token, event="ApproveHappyPath",
                       start="2025-09-01T10:30:00", end="2025-09-01T11:30:00")
    assert r.status_code == 201
    letter_id = r.json()["id"]

    r = client.post(f"/api/letters/{letter_id}/approve", headers=auth_hdr(coordinator_token))
    assert r.status_code == 200
    body = r.json()
    assert body["letter_id"] == letter_id
    assert len(body["affected_periods"]) > 0


def test_approve_letter_creates_attendance_records(client, student_token, coordinator_token):
    r = _submit_letter(client, student_token, event="ApproveAttendanceCheck",
                       start="2025-09-02T10:30:00", end="2025-09-02T11:30:00")
    letter_id = r.json()["id"]
    approve = client.post(f"/api/letters/{letter_id}/approve", headers=auth_hdr(coordinator_token))
    ap = approve.json()["affected_periods"][0]

    att = client.get("/api/attendance", params={"date": ap["date"], "period": ap["period_index"]},
                     headers=auth_hdr(coordinator_token))
    assert att.status_code == 200
    found = [row for row in att.json() if row["student_roll"] == "TST001"]
    assert found and found[0]["mark"] == "Present"
    assert found[0]["source"] == "SystemAuto"


def test_approve_letter_already_approved_returns_409(client, student_token, coordinator_token):
    r = _submit_letter(client, student_token, event="DoubleApproveTest",
                       start="2025-09-03T10:30:00", end="2025-09-03T11:30:00")
    letter_id = r.json()["id"]
    client.post(f"/api/letters/{letter_id}/approve", headers=auth_hdr(coordinator_token))
    r2 = client.post(f"/api/letters/{letter_id}/approve", headers=auth_hdr(coordinator_token))
    assert r2.status_code == 409


def test_approve_rejected_letter_returns_409(client, student_token, coordinator_token):
    r = _submit_letter(client, student_token, event="ApproveAfterRejectTest",
                       start="2025-09-05T10:30:00", end="2025-09-05T11:30:00")
    letter_id = r.json()["id"]
    client.post(f"/api/letters/{letter_id}/reject", json={}, headers=auth_hdr(coordinator_token))
    r2 = client.post(f"/api/letters/{letter_id}/approve", headers=auth_hdr(coordinator_token))
    assert r2.status_code == 409


def test_approve_letter_not_found_returns_404(client, coordinator_token):
    r = client.post("/api/letters/nonexistent-id/approve", headers=auth_hdr(coordinator_token))
    assert r.status_code == 404


def test_approve_letter_wrong_role_student(client, student_token):
    r = client.post("/api/letters/any-id/approve", headers=auth_hdr(student_token))
    assert r.status_code == 403


def test_approve_letter_wrong_role_teacher(client, teacher_token):
    r = client.post("/api/letters/any-id/approve", headers=auth_hdr(teacher_token))
    assert r.status_code == 403


def test_approve_multi_period_letter(client, student_token, coordinator_token):
    # Event spans periods 1, 2, 3 on a single day
    r = _submit_letter(client, student_token, event="MultiPeriodApprove",
                       start="2025-09-04T10:00:00", end="2025-09-04T13:00:00")
    assert r.status_code == 201
    letter_id = r.json()["id"]
    approve = client.post(f"/api/letters/{letter_id}/approve", headers=auth_hdr(coordinator_token))
    assert approve.status_code == 200
    assert len(approve.json()["affected_periods"]) >= 3


# ---------------------------------------------------------------------------
# Reject letter
# ---------------------------------------------------------------------------

def test_reject_letter_success(client, student_token, coordinator_token):
    r = _submit_letter(client, student_token, event="RejectHappyPath",
                       start="2025-10-01T10:30:00", end="2025-10-01T11:30:00")
    letter_id = r.json()["id"]
    r = client.post(f"/api/letters/{letter_id}/reject",
                    json={"comment": "Event not approved by college"},
                    headers=auth_hdr(coordinator_token))
    assert r.status_code == 200
    assert r.json()["status"] == "Rejected"


def test_reject_letter_saves_comment(client, student_token, coordinator_token):
    r = _submit_letter(client, student_token, event="RejectWithComment",
                       start="2025-10-02T10:30:00", end="2025-10-02T11:30:00")
    letter_id = r.json()["id"]
    client.post(f"/api/letters/{letter_id}/reject",
                json={"comment": "Insufficient documentation"},
                headers=auth_hdr(coordinator_token))
    detail = client.get(f"/api/letters/{letter_id}", headers=auth_hdr(coordinator_token))
    assert detail.json()["coordinator_comment"] == "Insufficient documentation"


def test_reject_letter_does_not_create_attendance(client, student_token, coordinator_token):
    r = _submit_letter(client, student_token, event="RejectNoAttendance",
                       start="2025-10-03T10:30:00", end="2025-10-03T11:30:00")
    letter_id = r.json()["id"]
    client.post(f"/api/letters/{letter_id}/reject", json={}, headers=auth_hdr(coordinator_token))
    att = client.get("/api/attendance", params={"date": "2025-10-03", "period": 1},
                     headers=auth_hdr(coordinator_token))
    found = [row for row in att.json() if row["student_roll"] == "TST001" and row["mark"] == "Present"]
    assert found == []


def test_reject_letter_wrong_role(client, student_token):
    r = client.post("/api/letters/any-id/reject", json={}, headers=auth_hdr(student_token))
    assert r.status_code == 403


def test_reject_already_rejected_no_409(client, student_token, coordinator_token):
    # Rejecting a Submitted letter twice is allowed (no guard on Rejected→Rejected transition)
    r = _submit_letter(client, student_token, event="DoubleRejectTest",
                       start="2025-10-04T10:30:00", end="2025-10-04T11:30:00")
    letter_id = r.json()["id"]
    client.post(f"/api/letters/{letter_id}/reject", json={}, headers=auth_hdr(coordinator_token))
    r2 = client.post(f"/api/letters/{letter_id}/reject", json={}, headers=auth_hdr(coordinator_token))
    assert r2.status_code == 200


def test_reject_approved_letter_returns_409(client, student_token, coordinator_token):
    r = _submit_letter(client, student_token, event="RejectAfterApproveTest",
                       start="2025-10-05T10:30:00", end="2025-10-05T11:30:00")
    letter_id = r.json()["id"]
    client.post(f"/api/letters/{letter_id}/approve", headers=auth_hdr(coordinator_token))
    r2 = client.post(f"/api/letters/{letter_id}/reject", json={}, headers=auth_hdr(coordinator_token))
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# List and get letters
# ---------------------------------------------------------------------------

def test_list_letters_coordinator_sees_all(client, coordinator_token):
    r = client.get("/api/letters", headers=auth_hdr(coordinator_token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_letters_coordinator_filter_by_status(client, coordinator_token):
    r = client.get("/api/letters?status=Submitted", headers=auth_hdr(coordinator_token))
    assert r.status_code == 200
    for letter in r.json():
        assert letter["status"] == "Submitted"


def test_list_letters_student_sees_only_own(client, student_token):
    r = client.get("/api/letters", headers=auth_hdr(student_token))
    assert r.status_code == 200
    for letter in r.json():
        assert letter["student_roll"] == "TST001"


def test_list_letters_teacher_forbidden(client, teacher_token):
    r = client.get("/api/letters", headers=auth_hdr(teacher_token))
    assert r.status_code == 403


def test_get_letter_coordinator_can_access_any(client, student_token, coordinator_token):
    r = _submit_letter(client, student_token, event="GetLetterCoord",
                       start="2025-11-01T10:30:00", end="2025-11-01T11:30:00")
    letter_id = r.json()["id"]
    r = client.get(f"/api/letters/{letter_id}", headers=auth_hdr(coordinator_token))
    assert r.status_code == 200
    assert r.json()["id"] == letter_id


def test_get_letter_student_can_access_own(client, student_token):
    r = _submit_letter(client, student_token, event="GetLetterOwnStudent",
                       start="2025-11-02T10:30:00", end="2025-11-02T11:30:00")
    letter_id = r.json()["id"]
    r = client.get(f"/api/letters/{letter_id}", headers=auth_hdr(student_token))
    assert r.status_code == 200


def test_get_letter_not_found_returns_404(client, coordinator_token):
    r = client.get("/api/letters/nonexistent-id", headers=auth_hdr(coordinator_token))
    assert r.status_code == 404
