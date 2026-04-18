"""CSV import tests: roster, teachers, timetable."""
import pytest
from backend.tests.conftest import auth_hdr

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upload(client, endpoint, csv_bytes, token, filename="data.csv"):
    return client.post(
        endpoint,
        files={"file": (filename, csv_bytes, "text/csv")},
        headers=auth_hdr(token),
    )


ROSTER_HEADERS = b"Roll Number,Name\n"
TEACHERS_HEADERS = b"Subject,Teacher Name\n"
TIMETABLE_HEADERS = b"Day,10:00-11:00,11:00-12:00,12:00-13:00,13:00-13:40,13:40-14:40,14:40-15:40,15:40-16:40\n"


# ---------------------------------------------------------------------------
# /api/import/teachers
# ---------------------------------------------------------------------------

def test_import_teachers_success(client, maintainer_token):
    csv = TEACHERS_HEADERS + b"MATH101,Prof. A. Kumar\nPHY101,Dr. B. Reddy\n"
    r = _upload(client, "/api/import/teachers", csv, maintainer_token)
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert r.json()["processed_rows"] == 2


def test_import_teachers_wrong_role_coordinator(client, coordinator_token):
    csv = TEACHERS_HEADERS + b"CHM101,Prof. Z\n"
    r = _upload(client, "/api/import/teachers", csv, coordinator_token)
    assert r.status_code == 403


def test_import_teachers_wrong_role_teacher(client, teacher_token):
    csv = TEACHERS_HEADERS + b"CHM101,Prof. Z\n"
    r = _upload(client, "/api/import/teachers", csv, teacher_token)
    assert r.status_code == 403


def test_import_teachers_wrong_headers(client, maintainer_token):
    csv = b"SubjectCode,TeacherName\nMATH,Prof. X\n"
    r = _upload(client, "/api/import/teachers", csv, maintainer_token)
    assert r.status_code == 400


def test_import_teachers_duplicate_subject_in_file(client, maintainer_token):
    csv = TEACHERS_HEADERS + b"DUPSUBJ,Prof. X\nDUPSUBJ,Prof. Y\n"
    r = _upload(client, "/api/import/teachers", csv, maintainer_token)
    assert r.status_code == 400
    assert "Duplicate" in r.text


def test_import_teachers_empty_subject_fails(client, maintainer_token):
    csv = TEACHERS_HEADERS + b",Prof. X\n"
    r = _upload(client, "/api/import/teachers", csv, maintainer_token)
    assert r.status_code == 400


def test_import_teachers_updates_existing_subject(client, maintainer_token):
    # Import MATH101 first with Prof. A, then re-import with Prof. B — should update teacher
    csv1 = TEACHERS_HEADERS + b"MATH_UPD,Prof. Original\n"
    csv2 = TEACHERS_HEADERS + b"MATH_UPD,Prof. Updated\n"
    r1 = _upload(client, "/api/import/teachers", csv1, maintainer_token)
    assert r1.status_code == 200
    r2 = _upload(client, "/api/import/teachers", csv2, maintainer_token)
    assert r2.status_code == 200


# ---------------------------------------------------------------------------
# /api/import/timetable
# ---------------------------------------------------------------------------

def test_import_timetable_success(client, maintainer_token):
    # First ensure TSUB has a teacher mapping (seeded in conftest)
    # Build a minimal timetable using TSUB
    csv = TIMETABLE_HEADERS + b"Wednesday,TSUB,,,,,,\n"
    r = _upload(client, "/api/import/timetable", csv, maintainer_token)
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_import_timetable_missing_teacher_mapping(client, maintainer_token):
    csv = TIMETABLE_HEADERS + b"Wednesday,UNKNOWN_SUBJ_XYZ,,,,,,\n"
    r = _upload(client, "/api/import/timetable", csv, maintainer_token)
    assert r.status_code == 400
    assert "Missing teacher mappings" in r.text


def test_import_timetable_wrong_role(client, coordinator_token):
    csv = TIMETABLE_HEADERS + b"Monday,TSUB,,,,,,\n"
    r = _upload(client, "/api/import/timetable", csv, coordinator_token)
    assert r.status_code == 403


def test_import_timetable_wrong_headers(client, maintainer_token):
    csv = b"Weekday,P1,P2,P3,P4,P5,P6,P7\nMonday,TSUB,,,,,,\n"
    r = _upload(client, "/api/import/timetable", csv, maintainer_token)
    assert r.status_code == 400


def test_import_timetable_lunch_marker_ignored(client, maintainer_token):
    # LUNCH in the lunch column should not require a teacher mapping
    csv = TIMETABLE_HEADERS + b"Thursday,TSUB,,,LUNCH,,,\n"
    r = _upload(client, "/api/import/timetable", csv, maintainer_token)
    assert r.status_code == 200


def test_import_timetable_replaces_all_entries(client, maintainer_token):
    # Two sequential imports: second should fully replace first
    csv1 = TIMETABLE_HEADERS + b"Friday,TSUB,,,,,,\n"
    csv2 = TIMETABLE_HEADERS + b"Saturday,TSUB,,,,,,\n"
    r1 = _upload(client, "/api/import/timetable", csv1, maintainer_token)
    r2 = _upload(client, "/api/import/timetable", csv2, maintainer_token)
    assert r1.status_code == 200
    assert r2.status_code == 200


# ---------------------------------------------------------------------------
# /api/import/roster
# ---------------------------------------------------------------------------

def test_import_roster_success(client, maintainer_token):
    csv = ROSTER_HEADERS + b"IMP001,Import One\nIMP002,Import Two\n"
    r = _upload(client, "/api/import/roster", csv, maintainer_token)
    assert r.status_code == 200
    assert r.json()["processed_rows"] == 2


def test_import_roster_wrong_role(client, coordinator_token):
    csv = ROSTER_HEADERS + b"IMP003,Import Three\n"
    r = _upload(client, "/api/import/roster", csv, coordinator_token)
    assert r.status_code == 403


def test_import_roster_wrong_headers(client, maintainer_token):
    csv = b"RollNo,StudentName\nIMP004,Import Four\n"
    r = _upload(client, "/api/import/roster", csv, maintainer_token)
    assert r.status_code == 400


def test_import_roster_duplicate_roll_in_file(client, maintainer_token):
    csv = ROSTER_HEADERS + b"DUP001,Student X\nDUP001,Student Y\n"
    r = _upload(client, "/api/import/roster", csv, maintainer_token)
    assert r.status_code == 400


def test_import_roster_duplicate_existing_in_db(client, maintainer_token):
    # TST001 already seeded in conftest
    csv = ROSTER_HEADERS + b"TST001,Student One Again\n"
    r = _upload(client, "/api/import/roster", csv, maintainer_token)
    assert r.status_code == 400
    assert "Already exists" in r.text


def test_import_roster_invalid_roll_format(client, maintainer_token):
    # Roll number with spaces violates schema pattern ^[A-Za-z0-9_.-]+$
    csv = ROSTER_HEADERS + b"INVALID ROLL,Bad Student\n"
    r = _upload(client, "/api/import/roster", csv, maintainer_token)
    assert r.status_code == 400
