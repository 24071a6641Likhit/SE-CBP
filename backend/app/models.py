import uuid
from sqlalchemy import Column, String, Integer, Text, Date, DateTime, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Student(Base):
    __tablename__ = "students"
    roll_number = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class Teacher(Base):
    __tablename__ = "teachers"
    teacher_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)


class Subject(Base):
    __tablename__ = "subjects"
    code = Column(String, primary_key=True)
    name = Column(String)
    teacher_id = Column(String(36), ForeignKey("teachers.teacher_id"), nullable=True)


class Timetable(Base):
    __tablename__ = "timetable"
    id = Column(Integer, primary_key=True, autoincrement=True)
    day_of_week = Column(String, nullable=False)
    period_index = Column(Integer, nullable=False)
    subject_code = Column(String, ForeignKey("subjects.code"), nullable=True)
    __table_args__ = (UniqueConstraint("day_of_week", "period_index", name="uq_day_period"),)


class Letter(Base):
    __tablename__ = "letters"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_roll = Column(String, ForeignKey("students.roll_number"), nullable=False)
    student_name = Column(String, nullable=False)
    event_name = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    start_datetime = Column(DateTime(timezone=True), nullable=False)
    end_datetime = Column(DateTime(timezone=True), nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, nullable=False, default="Submitted")
    coordinator_comment = Column(Text, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_roll = Column(String, ForeignKey("students.roll_number"), nullable=False)
    date = Column(Date, nullable=False)
    period_index = Column(Integer, nullable=False)
    mark = Column(String, nullable=False)
    source = Column(String, nullable=False)
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    version = Column(Integer, nullable=False, default=1)
    __table_args__ = (UniqueConstraint("student_roll", "date", "period_index", name="uq_student_date_period"),)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ts = Column(DateTime(timezone=True), server_default=func.now())
    actor_id = Column(String(36), nullable=True)
    action = Column(String, nullable=False)
    target = Column(String, nullable=False)
    prev_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    comment = Column(Text, nullable=True)
