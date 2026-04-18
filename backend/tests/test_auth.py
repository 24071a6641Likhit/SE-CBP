"""Auth tests: login, token validation, role-based access control."""
import pytest
from backend.tests.conftest import auth_hdr


def test_login_student_success(client, student_token):
    assert student_token is not None


def test_login_coordinator_success(client, coordinator_token):
    assert coordinator_token is not None


def test_login_teacher_returns_default_period(client):
    r = client.post("/api/auth/login", json={"username": "test_teacher_user", "password": "pass123"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    # default_period is int or None depending on time of day
    assert "default_period" in body


def test_login_bad_password(client):
    r = client.post("/api/auth/login", json={"username": "test_coordinator", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "ghost_user", "password": "pass123"})
    assert r.status_code == 401


def test_no_token_returns_401(client):
    r = client.get("/api/letters")
    assert r.status_code == 401


def test_invalid_token_returns_401(client):
    r = client.get("/api/letters", headers={"Authorization": "Bearer not.a.real.token"})
    assert r.status_code == 401


def test_malformed_auth_header_returns_401(client):
    r = client.get("/api/letters", headers={"Authorization": "Token something"})
    assert r.status_code == 401


# --- Role enforcement ---

def test_student_cannot_approve_letter(client, student_token):
    r = client.post("/api/letters/fake-id/approve", headers=auth_hdr(student_token))
    assert r.status_code == 403


def test_student_cannot_reject_letter(client, student_token):
    r = client.post("/api/letters/fake-id/reject", json={}, headers=auth_hdr(student_token))
    assert r.status_code == 403


def test_teacher_cannot_approve_letter(client, teacher_token):
    r = client.post("/api/letters/fake-id/approve", headers=auth_hdr(teacher_token))
    assert r.status_code == 403


def test_teacher_cannot_list_letters(client, teacher_token):
    r = client.get("/api/letters", headers=auth_hdr(teacher_token))
    assert r.status_code == 403


def test_student_cannot_access_audit(client, student_token):
    r = client.get("/api/audit", headers=auth_hdr(student_token))
    assert r.status_code == 403


def test_teacher_cannot_access_audit(client, teacher_token):
    r = client.get("/api/audit", headers=auth_hdr(teacher_token))
    assert r.status_code == 403


def test_coordinator_cannot_import_csv(client, coordinator_token):
    r = client.post(
        "/api/import/teachers",
        files={"file": ("teachers.csv", b"Subject,Teacher Name\nMATH,Prof. X", "text/csv")},
        headers=auth_hdr(coordinator_token),
    )
    assert r.status_code == 403


def test_student_cannot_import_csv(client, student_token):
    r = client.post(
        "/api/import/roster",
        files={"file": ("roster.csv", b"Roll Number,Name\nTEMP001,Temp", "text/csv")},
        headers=auth_hdr(student_token),
    )
    assert r.status_code == 403


def test_health_endpoint_no_auth(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"
