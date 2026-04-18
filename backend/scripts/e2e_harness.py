#!/usr/bin/env python3
"""End-to-end harness: imports CSVs, creates a test student user, submits a letter, approves it, and verifies attendance."""
import os
import time
import requests
from pathlib import Path
from datetime import datetime, date, time as dtime, timedelta

REPO = Path(__file__).resolve().parents[2]
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

SAMPLES = REPO / "samples"

MAINTAINER = {"username": "maintainer", "password": "changeme"}
COORDINATOR = {"username": "coordinator", "password": "changeme"}
TEACHER = {"username": "teacher", "password": "changeme"}
STUDENT_USERNAME = "student_test"
STUDENT_PASSWORD = "changeme"
TARGET_ROLL = "24071A6601"


def login(username, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def upload_csv(token, path, endpoint):
    with open(path, "rb") as fh:
        res = requests.post(f"{BASE_URL}{endpoint}", headers={"Authorization": f"Bearer {token}"}, files={"file": fh})
    # Do not raise on 400 here; caller will inspect and decide
    try:
        return res.json()
    except Exception:
        return {"status_code": res.status_code, "text": res.text}


def create_student_user_in_db(username, password, roll):
    # create user and link to existing student via direct DB access
    import backend.app.database as dbmod
    from backend.app import models, auth
    db = dbmod.SessionLocal()
    try:
        u = db.query(models.User).filter_by(username=username).first()
        if not u:
            u = models.User(username=username, password_hash=auth.get_password_hash(password), role='student')
            db.add(u)
            db.flush()
        st = db.query(models.Student).filter_by(roll_number=roll).first()
        if not st:
            st = models.Student(roll_number=roll, name="Test Student", user_id=u.id)
            db.add(st)
        else:
            st.user_id = u.id
        db.commit()
        return u
    finally:
        db.close()


def main():
    print("1) Login as maintainer")
    mtoken = login(MAINTAINER["username"], MAINTAINER["password"])
    print("2) Upload roster")
    resp = upload_csv(mtoken, SAMPLES / "roster.csv", "/api/import/roster")
    print(resp)
    print("3) Upload teachers")
    resp = upload_csv(mtoken, SAMPLES / "teachers.csv", "/api/import/teachers")
    print(resp)
    print("4) Upload timetable")
    resp = upload_csv(mtoken, SAMPLES / "timetable.csv", "/api/import/timetable")
    print(resp)

    print("5) Ensure test student user exists and is linked to roster roll")
    create_student_user_in_db(STUDENT_USERNAME, STUDENT_PASSWORD, TARGET_ROLL)

    print("6) Student login and submit letter")
    stoken = login(STUDENT_USERNAME, STUDENT_PASSWORD)

    # choose today's date and times overlapping P3 (12:00-13:00)
    today = date.today().isoformat()
    start_dt = f"{today}T12:05:00"
    end_dt = f"{today}T13:05:00"
    payload = {
        "student_roll": TARGET_ROLL,
        "student_name": "Test Student",
        "event_name": "Test Event",
        "start_datetime": start_dt,
        "end_datetime": end_dt,
        "body": "Automated test event"
    }
    r = requests.post(f"{BASE_URL}/api/letters", headers={"Authorization": f"Bearer {stoken}"}, json=payload)
    r.raise_for_status()
    letter = r.json()
    print("Letter created:", letter)

    print("7) Coordinator approves")
    ctoken = login(COORDINATOR["username"], COORDINATOR["password"])
    r = requests.post(f"{BASE_URL}/api/letters/{letter['id']}/approve", headers={"Authorization": f"Bearer {ctoken}"})
    r.raise_for_status()
    print("Approved response:", r.json())

    print("8) Teacher checks attendance for P3")
    ttoken = login(TEACHER["username"], TEACHER["password"])
    today_date = date.today().isoformat()
    r = requests.get(f"{BASE_URL}/api/attendance", headers={"Authorization": f"Bearer {ttoken}"}, params={"date": today_date, "period": 3})
    r.raise_for_status()
    attends = r.json()
    found = [a for a in attends if a["student_roll"] == TARGET_ROLL]
    if not found:
        print("Student not found in attendance list")
    else:
        print("Attendance row:", found[0])
        assert found[0]["mark"] == "Present", "Attendance was not marked Present"
        print("E2E success: attendance is Present")


if __name__ == '__main__':
    main()
