import io
import csv
import json
from pathlib import Path
from datetime import datetime, date, time, timedelta
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jsonschema import validate, ValidationError
from dateutil import parser as dateparser
from fastapi.responses import JSONResponse
import logging
import os

from . import models, auth
from .database import SessionLocal, init_db
from .ws import manager
import uuid

app = FastAPI(title="College Event Attendance Coordination API (MVP)")

# CORS - allow frontend dev origins; for MVP allow all origins (configure in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

PERIODS = [
    (1, time(10, 0), time(11, 0)),
    (2, time(11, 0), time(12, 0)),
    (3, time(12, 0), time(13, 0)),
    # lunch 13:00-13:40 skipped
    (4, time(13, 40), time(14, 40)),
    (5, time(14, 40), time(15, 40)),
    (6, time(15, 40), time(16, 40)),
]


from datetime import timezone


def _to_local_naive(dt: datetime) -> datetime:
    """Convert an aware datetime to the system local timezone and return a naive datetime.

    If dt is already naive, return it unchanged.
    """
    if dt is None:
        return dt
    if dt.tzinfo is not None:
        # convert to system local timezone then strip tzinfo
        local_tz = datetime.now().astimezone().tzinfo
        return dt.astimezone(local_tz).replace(tzinfo=None)
    return dt


# configure logger
logger = logging.getLogger("uvicorn.error")


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Do not leak internal details in production. When DEBUG env var is set, include exception text.
    debug = os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes")
    logger.exception("Unhandled exception for request %s %s", request.method, request.url)
    content = {"code": "internal_error", "message": "Internal server error"}
    if debug:
        content["details"] = str(exc)
    return JSONResponse(status_code=500, content=content)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    default_period: Optional[int] = None


class LetterCreateRequest(BaseModel):
    student_roll: str
    student_name: str
    event_name: str
    start_datetime: str
    end_datetime: str
    body: Optional[str] = None


class ApproveResponse(BaseModel):
    letter_id: str
    affected_periods: List[dict]


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from jose import JWTError
    try:
        payload = auth.decode_access_token(token)
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    user = db.query(models.User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    # Accept token as query param: /ws?token=<jwt>
    await websocket.accept()
    if not token:
        await websocket.close(code=1008)
        return
    try:
        payload = auth.decode_access_token(token)
        username = payload.get("sub")
    except Exception:
        await websocket.close(code=1008)
        return
    # create a DB session to resolve user id and role
    db = SessionLocal()
    try:
        user = db.query(models.User).filter_by(username=username).first()
        if not user:
            await websocket.close(code=1008)
            return
        await manager.connect(websocket, user.id, user.role)
        while True:
            try:
                msg = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except Exception:
                # ignore malformed messages
                continue
            # handle ack messages
            if isinstance(msg, dict) and msg.get("type") == "ack" and msg.get("id"):
                await manager.handle_ack(msg.get("id"), user.id)
    finally:
        try:
            await manager.disconnect(websocket)
        finally:
            db.close()


def event_to_periods(start_dt: datetime, end_dt: datetime):
    result = []
    current_date = start_dt.date()
    last_date = end_dt.date()
    while current_date <= last_date:
        for p_index, p_start_time, p_end_time in PERIODS:
            p_start_dt = datetime.combine(current_date, p_start_time)
            p_end_dt = datetime.combine(current_date, p_end_time)
            if start_dt < p_end_dt and end_dt > p_start_dt:
                result.append({"date": p_start_dt.date().isoformat(), "period_index": p_index})
        current_date = current_date + timedelta(days=1)
    return result


def get_current_period(now_dt: Optional[datetime] = None):
    """Return tuple (day_of_week, period_index) based on system local time.
    day_of_week uses full name e.g., 'Monday'. If no period matched, returns (day, None).
    """
    if now_dt is None:
        now_dt = datetime.now()
    tnow = now_dt.time()
    for pindex, pstart, pend in PERIODS:
        if pstart <= tnow <= pend:
            return (now_dt.strftime('%A'), pindex)
    # Outside all periods — snap to boundary or next upcoming period (e.g. during lunch gap)
    if tnow < PERIODS[0][1]:
        return (now_dt.strftime('%A'), PERIODS[0][0])
    if tnow > PERIODS[-1][2]:
        return (now_dt.strftime('%A'), PERIODS[-1][0])
    # In a gap between periods (e.g. lunch 13:00–13:40) — return the next upcoming period
    for pindex, pstart, pend in PERIODS:
        if tnow < pstart:
            return (now_dt.strftime('%A'), pindex)
    return (now_dt.strftime('%A'), PERIODS[-1][0])


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.post("/api/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(username=body.username).first()
    if not user or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = auth.create_access_token({"sub": user.username, "role": user.role, "user_id": user.id})
    default_period = None
    if user.role == "teacher":
        now_local = datetime.now()
        tnow = now_local.time()
        for pindex, pstart, pend in PERIODS:
            if pstart <= tnow <= pend:
                default_period = pindex
                break
        if default_period is None:
            # after last period -> last; before first -> first
            if tnow > PERIODS[-1][2]:
                default_period = PERIODS[-1][0]
            else:
                default_period = PERIODS[0][0]
    return {"access_token": token, "token_type": "Bearer", "default_period": default_period}


@app.post("/api/import/roster")
async def import_roster(file: UploadFile = File(...), db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "maintainer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only maintainer may import CSVs")

    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "schemas" / "roster.json"
    if not schema_path.exists():
        raise HTTPException(status_code=500, detail="Roster schema missing on server")
    schema = json.loads(schema_path.read_text())

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    expected_headers = schema.get("x-import", {}).get("headers")
    if expected_headers and reader.fieldnames != expected_headers:
        raise HTTPException(status_code=400, detail={"message": "Invalid CSV headers", "expected": expected_headers, "found": reader.fieldnames})

    rows = list(reader)
    errors = []
    cleaned_rows = []
    seen = set()
    for idx, row in enumerate(rows, start=2):
        cleaned = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        try:
            validate(cleaned, schema)
        except ValidationError as ve:
            errors.append({"row": idx, "message": ve.message})
            continue
        roll = cleaned.get("Roll Number")
        if roll in seen:
            errors.append({"row": idx, "message": "Duplicate roll number in file"})
            continue
        seen.add(roll)
        cleaned_rows.append(cleaned)

    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    # check DB duplicates
    existing = db.query(models.Student).filter(models.Student.roll_number.in_(list(seen))).all()
    if existing:
        errors = [{"roll_number": s.roll_number, "message": "Already exists in database"} for s in existing]
        raise HTTPException(status_code=400, detail={"errors": errors})

    # insert students
    for r in cleaned_rows:
        st = models.Student(roll_number=r["Roll Number"], name=r["Name"])
        db.add(st)
    db.commit()
    return {"success": True, "processed_rows": len(cleaned_rows), "errors": []}


@app.post("/api/import/teachers")
async def import_teachers(file: UploadFile = File(...), db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "maintainer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only maintainer may import CSVs")

    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "schemas" / "teachers.json"
    if not schema_path.exists():
        raise HTTPException(status_code=500, detail="Teacher schema missing on server")
    schema = json.loads(schema_path.read_text())

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    expected_headers = schema.get("x-import", {}).get("headers")
    if expected_headers and reader.fieldnames != expected_headers:
        raise HTTPException(status_code=400, detail={"message": "Invalid CSV headers", "expected": expected_headers, "found": reader.fieldnames})

    rows = list(reader)
    errors = []
    cleaned_rows = []
    seen = set()
    for idx, row in enumerate(rows, start=2):
        cleaned = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        try:
            validate(cleaned, schema)
        except ValidationError as ve:
            errors.append({"row": idx, "message": ve.message})
            continue
        subj = cleaned.get("Subject")
        if subj in seen:
            errors.append({"row": idx, "message": "Duplicate subject in file"})
            continue
        seen.add(subj)
        cleaned_rows.append(cleaned)

    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    # Persist teachers and subjects
    for r in cleaned_rows:
        subj = r["Subject"]
        tname = r["Teacher Name"]
        teacher = db.query(models.Teacher).filter_by(name=tname).first()
        if not teacher:
            teacher = models.Teacher(name=tname)
            db.add(teacher)
            db.flush()
        subject = db.query(models.Subject).filter_by(code=subj).first()
        if subject:
            subject.teacher_id = teacher.teacher_id
        else:
            subject = models.Subject(code=subj, name=subj, teacher_id=teacher.teacher_id)
            db.add(subject)
    db.commit()
    return {"success": True, "processed_rows": len(cleaned_rows), "errors": []}


@app.post("/api/import/timetable")
async def import_timetable(file: UploadFile = File(...), db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "maintainer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only maintainer may import CSVs")

    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "schemas" / "timetable.json"
    if not schema_path.exists():
        raise HTTPException(status_code=500, detail="Timetable schema missing on server")
    schema = json.loads(schema_path.read_text())

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    expected_headers = schema.get("x-import", {}).get("headers")
    if expected_headers and reader.fieldnames != expected_headers:
        raise HTTPException(status_code=400, detail={"message": "Invalid CSV headers", "expected": expected_headers, "found": reader.fieldnames})

    rows = list(reader)
    errors = []
    cleaned_rows = []
    for idx, row in enumerate(rows, start=2):
        cleaned = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        try:
            validate(cleaned, schema)
        except ValidationError as ve:
            errors.append({"row": idx, "message": ve.message})
            continue
        cleaned_rows.append(cleaned)

    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    period_map = schema.get("x-import", {}).get("periodMap", {})
    missing_mappings = []
    for r in cleaned_rows:
        for col, pindex in period_map.items():
            subj = r.get(col)
            if subj and subj.strip():
                # Skip lunch marker
                if subj.strip().upper() == "LUNCH":
                    continue
                s = db.query(models.Subject).filter_by(code=subj).first()
                if not s or not s.teacher_id:
                    missing_mappings.append({"day": r.get("Day"), "period_col": col, "subject": subj})

    if missing_mappings:
        raise HTTPException(status_code=400, detail={"message": "Missing teacher mappings for subjects", "details": missing_mappings})

    # Replace timetable with imported rows (transactional by design)
    db.query(models.Timetable).delete()
    for r in cleaned_rows:
        day = r.get("Day")
        for col, pindex in period_map.items():
            subj = r.get(col)
            if subj and subj.strip():
                tt = models.Timetable(day_of_week=day, period_index=pindex, subject_code=subj)
                db.add(tt)
    db.commit()
    return {"success": True, "processed_rows": len(cleaned_rows), "errors": []}


@app.post("/api/letters", status_code=201)
async def create_letter(body: LetterCreateRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    student = db.query(models.Student).filter_by(roll_number=body.student_roll).first()
    if not student:
        raise HTTPException(status_code=400, detail="Student not found in roster")
    try:
        start_dt = dateparser.parse(body.start_datetime)
        end_dt = dateparser.parse(body.end_datetime)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid datetime format; use ISO8601")

    # if incoming datetimes are timezone-aware, log conversion and normalize to system-local naive datetimes
    try:
        if getattr(start_dt, "tzinfo", None) is not None or getattr(end_dt, "tzinfo", None) is not None:
            logger.info("Converting timezone-aware datetimes to system-local: start=%s end=%s", getattr(start_dt, "isoformat", lambda: str(start_dt))(), getattr(end_dt, "isoformat", lambda: str(end_dt))())
        start_dt = _to_local_naive(start_dt)
        end_dt = _to_local_naive(end_dt)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid datetime values")
    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="start_datetime must be before end_datetime")
    affected = event_to_periods(start_dt, end_dt)
    if not affected:
        # include parsed datetimes to help debug client/server timezone/format mismatches
        raise HTTPException(status_code=400, detail={"message": "Event does not overlap any college period", "start": start_dt.isoformat(), "end": end_dt.isoformat()})
    letter = models.Letter(student_roll=body.student_roll, student_name=body.student_name, event_name=body.event_name, content=body.body if hasattr(body, 'body') else None, start_datetime=start_dt, end_datetime=end_dt, status="Submitted")
    db.add(letter)
    db.commit()
    db.refresh(letter)
    # emit realtime event to coordinator clients
    event = {
        "id": str(uuid.uuid4()),
        "type": "letter.created",
        "published_at": datetime.utcnow().isoformat() + "Z",
        "payload": {"letter_id": letter.id, "student_roll": letter.student_roll, "submitted_at": letter.submitted_at.isoformat()},
        "requires_ack": True,
    }
    try:
        await manager.broadcast(event, ["coordinator"])
    except Exception:
        pass
    print(f"letter.created {letter.id} student={letter.student_roll}")
    return {"id": letter.id, "student_roll": letter.student_roll, "submitted_at": letter.submitted_at.isoformat(), "status": letter.status, "content": letter.content}


@app.post("/api/letters/{letter_id}/approve")
async def approve_letter(letter_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "coordinator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only coordinator may approve")
    letter = db.query(models.Letter).filter_by(id=letter_id).first()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")
    if letter.status != "Submitted":
        raise HTTPException(status_code=409, detail=f"Cannot approve a {letter.status} letter; only Submitted letters can be approved")
    affected = event_to_periods(letter.start_datetime, letter.end_datetime)
    now = datetime.utcnow()
    for ap in affected:
        adate = date.fromisoformat(ap["date"])
        pindex = ap["period_index"]
        attendance = db.query(models.AttendanceRecord).filter_by(student_roll=letter.student_roll, date=adate, period_index=pindex).first()
        prev = attendance.mark if attendance else None
        if attendance:
            attendance.mark = "Present"
            attendance.source = "SystemAuto"
            attendance.updated_by = current_user.id
            attendance.updated_at = now
            attendance.version = (attendance.version or 1) + 1
            db.add(models.AuditLog(actor_id=current_user.id, action="attendance.update", target=f"{letter.student_roll}:{adate.isoformat()}:{pindex}", prev_value={"mark": prev} if prev else None, new_value={"mark": "Present"}, comment="Auto-applied by coordinator approval"))
        else:
            new_att = models.AttendanceRecord(student_roll=letter.student_roll, date=adate, period_index=pindex, mark="Present", source="SystemAuto", updated_by=current_user.id, updated_at=now, version=1)
            db.add(new_att)
            db.add(models.AuditLog(actor_id=current_user.id, action="attendance.create", target=f"{letter.student_roll}:{adate.isoformat()}:{pindex}", prev_value=None, new_value={"mark": "Present"}, comment="Auto-created by coordinator approval"))
    letter.status = "Approved"
    letter.approved_at = now
    letter.approved_by = current_user.id
    db.add(models.AuditLog(actor_id=current_user.id, action="letter.approve", target=f"letter:{letter.id}", prev_value={"status": "Submitted"}, new_value={"status": "Approved"}, comment="Coordinator approval"))
    db.commit()
    # emit realtime event to teachers (and coordinator)
    event = {
        "id": str(uuid.uuid4()),
        "type": "letter.approved",
        "published_at": datetime.utcnow().isoformat() + "Z",
        "payload": {"letter_id": letter.id, "affected_periods": affected, "student_roll": letter.student_roll},
        "requires_ack": True,
    }
    try:
        await manager.broadcast(event, ["teacher", "coordinator"])
    except Exception:
        pass
    print(f"letter.approved {letter.id} affected={affected}")
    return {"letter_id": letter.id, "affected_periods": affected}


@app.post("/api/debug/broadcast")
async def debug_broadcast(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Maintainer-only debug helper to broadcast custom events
    if current_user.role != "maintainer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only maintainer may broadcast events")
    ev_type = payload.get("type")
    roles = payload.get("roles", [])
    body = payload.get("payload", {})
    requires_ack = payload.get("requires_ack", False)
    event = {"id": str(uuid.uuid4()), "type": ev_type or "debug.event", "published_at": datetime.utcnow().isoformat() + "Z", "payload": body, "requires_ack": requires_ack}
    await manager.broadcast(event, roles or ["coordinator", "teacher"])
    return {"sent": True, "event_id": event["id"]}


@app.get("/api/letters")
def list_letters(status: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Coordinator: list all (optionally filtered by status)
    if current_user.role == "coordinator":
        q = db.query(models.Letter)
        if status:
            q = q.filter(models.Letter.status == status)
        rows = q.order_by(models.Letter.submitted_at.desc()).limit(limit).all()
    elif current_user.role == "student":
        st = db.query(models.Student).filter_by(user_id=current_user.id).first()
        if not st:
            return []
        rows = db.query(models.Letter).filter_by(student_roll=st.roll_number).order_by(models.Letter.submitted_at.desc()).limit(limit).all()
    else:
        raise HTTPException(status_code=403, detail="Insufficient privileges")
    return [{"id": r.id, "student_roll": r.student_roll, "student_name": r.student_name, "event_name": r.event_name, "content": r.content, "start_datetime": r.start_datetime.isoformat(), "end_datetime": r.end_datetime.isoformat(), "status": r.status, "submitted_at": r.submitted_at.isoformat()} for r in rows]


@app.get("/api/letters/{letter_id}")
def get_letter(letter_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    letter = db.query(models.Letter).filter_by(id=letter_id).first()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")
    if current_user.role == "coordinator":
        pass
    elif current_user.role == "student":
        st = db.query(models.Student).filter_by(user_id=current_user.id).first()
        if not st or st.roll_number != letter.student_roll:
            raise HTTPException(status_code=403, detail="Not allowed")
    else:
        raise HTTPException(status_code=403, detail="Not allowed")
    return {"id": letter.id, "student_roll": letter.student_roll, "student_name": letter.student_name, "event_name": letter.event_name, "content": letter.content, "start_datetime": letter.start_datetime.isoformat(), "end_datetime": letter.end_datetime.isoformat(), "status": letter.status, "submitted_at": letter.submitted_at.isoformat(), "coordinator_comment": letter.coordinator_comment}


@app.post("/api/letters/{letter_id}/reject")
async def reject_letter(letter_id: str, payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "coordinator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only coordinator may reject")
    letter = db.query(models.Letter).filter_by(id=letter_id).first()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")
    if letter.status == "Approved":
        raise HTTPException(status_code=409, detail="Approved letter cannot be rejected; attendance records already committed")
    comment = payload.get("comment") if isinstance(payload, dict) else None
    prev = {"status": letter.status}
    letter.status = "Rejected"
    letter.coordinator_comment = comment
    db.add(models.AuditLog(actor_id=current_user.id, action="letter.reject", target=f"letter:{letter.id}", prev_value=prev, new_value={"status": "Rejected"}, comment=comment))
    db.commit()
    # notify student via realtime (optional)
    event = {"id": str(uuid.uuid4()), "type": "letter.rejected", "published_at": datetime.utcnow().isoformat() + "Z", "payload": {"letter_id": letter.id, "student_roll": letter.student_roll, "comment": comment}, "requires_ack": False}
    try:
        # send to coordinator and student roles
        await manager.broadcast(event, ["coordinator"])
    except Exception:
        pass
    return {"letter_id": letter.id, "status": "Rejected"}


@app.get("/api/audit")
def query_audit(start: Optional[str] = None, end: Optional[str] = None, actor_id: Optional[str] = None, limit: int = 200, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Maintainer or coordinator only for MVP
    if current_user.role not in ("maintainer", "coordinator"):
        raise HTTPException(status_code=403, detail="Insufficient privileges")
    q = db.query(models.AuditLog)
    if actor_id:
        q = q.filter(models.AuditLog.actor_id == actor_id)
    if start:
        try:
            sdt = date.fromisoformat(start)
            q = q.filter(models.AuditLog.ts >= datetime.combine(sdt, time.min))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid start date format")
    if end:
        try:
            edt = date.fromisoformat(end)
            q = q.filter(models.AuditLog.ts <= datetime.combine(edt, time.max))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid end date format")
    rows = q.order_by(models.AuditLog.ts.desc()).limit(limit).all()
    return [{"id": r.id, "ts": r.ts.isoformat(), "actor_id": r.actor_id, "action": r.action, "target": r.target, "prev_value": r.prev_value, "new_value": r.new_value, "comment": r.comment} for r in rows]


@app.get("/api/attendance")
def get_attendance(date_str: str = Query(..., alias="date"), period: int = Query(..., alias="period"), db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        adate = date.fromisoformat(date_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date, use YYYY-MM-DD")
    students = db.query(models.Student).order_by(models.Student.roll_number).all()
    result = []
    for s in students:
        attendance = db.query(models.AttendanceRecord).filter_by(student_roll=s.roll_number, date=adate, period_index=period).first()
        mark = attendance.mark if attendance else "Absent"
        source = attendance.source if attendance else "Manual"
        version = attendance.version if attendance else None
        updated_at = attendance.updated_at.isoformat() if attendance and attendance.updated_at else None
        result.append({"student_roll": s.roll_number, "student_name": s.name, "mark": mark, "source": source, "version": version, "updated_at": updated_at})
    return result


@app.get("/api/current_period")
def api_current_period(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    day, period = get_current_period()
    # fetch subject and teacher assignment for current period
    tt = db.query(models.Timetable).filter_by(day_of_week=day, period_index=period).first()
    subject = None
    teacher_name = None
    assigned = False
    if tt and tt.subject_code:
        subj = db.query(models.Subject).filter_by(code=tt.subject_code).first()
        if subj:
            subject = {"code": subj.code, "name": subj.name}
            if subj.teacher_id:
                t = db.query(models.Teacher).filter_by(teacher_id=subj.teacher_id).first()
                if t:
                    teacher_name = t.name
                    assigned = True
    return {"day": day, "period": period, "subject": subject, "teacher_name": teacher_name, "assigned": assigned}


@app.post("/api/attendance")
def update_attendance(payload: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    updates = payload.get("updates", [])
    if not isinstance(updates, list):
        raise HTTPException(status_code=400, detail="Invalid payload")
    changed = 0
    warnings = []
    # determine current period for teacher enforcement
    current_day, current_period = get_current_period()
    for u in updates:
        s_roll = u.get("student_roll")
        date_str = u.get("date")
        pindex = u.get("period_index")
        mark = u.get("mark")
        version = u.get("version")
        if not all([s_roll, date_str, mark]) or pindex is None:
            continue
        try:
            adate = date.fromisoformat(date_str)
        except Exception:
            continue
        # If user is teacher, enforce they can only mark for current period and their assigned subject
        if current_user.role == "teacher":
            # ensure date is today
            today_str = datetime.now().date().isoformat()
            if date_str != today_str or pindex != current_period:
                raise HTTPException(status_code=403, detail="Unauthorized period access: can only mark current period for today")
            # check timetable assignment
            day_name = datetime.now().strftime('%A')
            tt = db.query(models.Timetable).filter_by(day_of_week=day_name, period_index=pindex).first()
            if not tt or not tt.subject_code:
                raise HTTPException(status_code=403, detail="No subject/timetable entry for current period")
            subject = db.query(models.Subject).filter_by(code=tt.subject_code).first()
            if not subject or not subject.teacher_id:
                raise HTTPException(status_code=403, detail="No teacher assigned to subject for this period")
            teacher = db.query(models.Teacher).filter_by(teacher_id=subject.teacher_id).first()
            if not teacher or teacher.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Unauthorized period access: you are not the assigned teacher for this period")
        record = db.query(models.AttendanceRecord).filter_by(student_roll=s_roll, date=adate, period_index=pindex).first()
        if record:
            # allow update but note it existed
            if version is not None and version != record.version:
                raise HTTPException(status_code=409, detail="Version conflict")
            prev = record.mark
            record.mark = mark
            record.source = "Manual"
            record.updated_by = current_user.id
            record.updated_at = datetime.utcnow()
            record.version = (record.version or 1) + 1
            db.add(models.AuditLog(actor_id=current_user.id, action="attendance.update", target=f"{s_roll}:{adate.isoformat()}:{pindex}", prev_value={"mark": prev}, new_value={"mark": mark}, comment="Teacher edit"))
            changed += 1
            warnings.append({"student_roll": s_roll, "message": "Attendance already provided; updated"})
        else:
            new_rec = models.AttendanceRecord(student_roll=s_roll, date=adate, period_index=pindex, mark=mark, source="Manual", updated_by=current_user.id, updated_at=datetime.utcnow(), version=1)
            db.add(new_rec)
            db.add(models.AuditLog(actor_id=current_user.id, action="attendance.create", target=f"{s_roll}:{adate.isoformat()}:{pindex}", prev_value=None, new_value={"mark": mark}, comment="Teacher create"))
            changed += 1
    db.commit()
    resp = {"updated": changed}
    if warnings:
        resp["warnings"] = warnings
    return resp


if __name__ == "__main__":
    print("Run with: uvicorn backend.app.main:app --reload --port 8000")
