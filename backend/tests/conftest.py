import os
import tempfile
import pytest

_TMP_DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.database import init_db, SessionLocal  # noqa: E402
from backend.app import models, auth  # noqa: E402
from backend.app.main import app  # noqa: E402


def _add_user(db, username, password, role):
    u = models.User(username=username, password_hash=auth.get_password_hash(password), role=role)
    db.add(u)
    db.flush()
    return u


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    if os.path.exists(_TMP_DB):
        os.remove(_TMP_DB)
    init_db()
    db = SessionLocal()
    try:
        _add_user(db, "test_maintainer", "pass123", "maintainer")
        _add_user(db, "test_coordinator", "pass123", "coordinator")

        tu = _add_user(db, "test_teacher_user", "pass123", "teacher")
        teacher = models.Teacher(name="Test Teacher", user_id=tu.id)
        db.add(teacher)
        db.flush()
        db.add(models.Subject(code="TSUB", name="Test Subject", teacher_id=teacher.teacher_id))

        tu2 = _add_user(db, "test_teacher2_user", "pass123", "teacher")
        db.add(models.Teacher(name="Test Teacher Two", user_id=tu2.id))

        for roll, name in [("TST001", "Student One"), ("TST002", "Student Two"), ("TST003", "Student Three")]:
            su = _add_user(db, f"{roll.lower()}@test.in", "pass123", "student")
            db.add(models.Student(roll_number=roll, name=name, user_id=su.id))

        db.commit()
    finally:
        db.close()
    yield
    if os.path.exists(_TMP_DB):
        os.remove(_TMP_DB)


@pytest.fixture(scope="session")
def client(setup_database):
    return TestClient(app)


def _get_token(client, username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"Login failed for {username}: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def maintainer_token(client):
    return _get_token(client, "test_maintainer", "pass123")


@pytest.fixture(scope="session")
def coordinator_token(client):
    return _get_token(client, "test_coordinator", "pass123")


@pytest.fixture(scope="session")
def teacher_token(client):
    return _get_token(client, "test_teacher_user", "pass123")


@pytest.fixture(scope="session")
def teacher2_token(client):
    return _get_token(client, "test_teacher2_user", "pass123")


@pytest.fixture(scope="session")
def student_token(client):
    return _get_token(client, "tst001@test.in", "pass123")


def auth_hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def timetable_monday_p1(setup_database):
    """Creates Timetable entry Monday/period1/TSUB, cleans up after test."""
    db = SessionLocal()
    try:
        db.query(models.Timetable).filter_by(day_of_week="Monday", period_index=1).delete()
        tt = models.Timetable(day_of_week="Monday", period_index=1, subject_code="TSUB")
        db.add(tt)
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(models.Timetable).filter_by(day_of_week="Monday", period_index=1).delete()
        db.commit()
    finally:
        db.close()
