-- Postgres DDL for College Event Attendance Coordination System (MVP)

-- Enable pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Users (auth accounts)
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('student','coordinator','teacher','maintainer')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Students
CREATE TABLE IF NOT EXISTS students (
  roll_number TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL
);

-- Teachers
CREATE TABLE IF NOT EXISTS teachers (
  teacher_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  user_id UUID REFERENCES users(id)
);

-- Subjects
CREATE TABLE IF NOT EXISTS subjects (
  code TEXT PRIMARY KEY,
  name TEXT,
  teacher_id UUID REFERENCES teachers(teacher_id)
);

-- Timetable (day + period -> subject)
CREATE TABLE IF NOT EXISTS timetable (
  id SERIAL PRIMARY KEY,
  day_of_week TEXT NOT NULL,
  period_index SMALLINT NOT NULL,
  subject_code TEXT REFERENCES subjects(code),
  UNIQUE (day_of_week, period_index)
);

-- Letters (student-submitted events)
CREATE TABLE IF NOT EXISTS letters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_roll TEXT NOT NULL REFERENCES students(roll_number),
  student_name TEXT NOT NULL,
  event_name TEXT NOT NULL,
  content TEXT,
  start_datetime TIMESTAMPTZ NOT NULL,
  end_datetime TIMESTAMPTZ NOT NULL,
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL CHECK (status IN ('Submitted','Approved','Rejected')) DEFAULT 'Submitted',
  coordinator_comment TEXT,
  approved_at TIMESTAMPTZ,
  approved_by UUID REFERENCES users(id)
);

-- Attendance records (one row per student/date/period)
CREATE TABLE IF NOT EXISTS attendance_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_roll TEXT NOT NULL REFERENCES students(roll_number),
  date DATE NOT NULL,
  period_index SMALLINT NOT NULL,
  mark TEXT NOT NULL CHECK (mark IN ('Present','Absent')),
  source TEXT NOT NULL CHECK (source IN ('Manual','SystemAuto')),
  updated_by UUID REFERENCES users(id),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  version INTEGER NOT NULL DEFAULT 1,
  UNIQUE (student_roll, date, period_index)
);

CREATE INDEX IF NOT EXISTS idx_attendance_date_period ON attendance_records(date, period_index);

-- Audit log (append-only semantics enforced by policy / application)
CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor_id UUID,
  action TEXT NOT NULL,
  target TEXT NOT NULL,
  prev_value JSONB,
  new_value JSONB,
  comment TEXT
);

-- Helper: ensure event->period mapping queries are fast
CREATE INDEX IF NOT EXISTS idx_timetable_day_period ON timetable(day_of_week, period_index);

-- Notes:
-- - All updates to attendance_records should be performed in transactions.
-- - For teacher edits, use optimistic concurrency: client must supply `version`; server rejects updates when version mismatch (HTTP 409).
-- - When coordinator approves a letter, server computes affected periods and within a transaction upserts attendance_records
--   for the affected (student_roll,date,period_index) rows, setting mark='Present', source='SystemAuto', updating version++, and inserting audit_log entries.

