# College Event Attendance System

This repository contains a full-stack project for managing attendance and permission-letter workflows for college events.

## Project Structure

- `backend/` - FastAPI service, auth, attendance APIs, WebSocket notifications, and tests.
- `frontend/` - React + Vite user interface for student, coordinator, and teacher roles.
- `import/` - CSV import rules and related documentation.
- `db/` - SQL schema definition used for initialization/reference.
- `schemas/` - JSON Schemas for validating import files.
- `samples/` - Sample CSV files for roster, timetable, and teacher mapping.
- `design/` - OpenAPI spec, sequence diagrams, and design artifacts.
- `sample_mdj_files/` - External/reference `.mdj` diagram examples.
- `College_Event_Attendance_SRS.md` - Software requirements specification.

## Quick Start

### Backend

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r backend/requirements.txt`
3. Initialize database:
   - `python backend/init_db.py`
4. Run API server:
   - `uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000`

### Frontend

1. Go to frontend:
   - `cd frontend`
2. Install dependencies:
   - `npm install`
3. Start development server:
   - `npm run dev`

## Default Test Credentials

- `maintainer` / `changeme`
- `coordinator` / `changeme`
- `teacher` / `changeme`
- `student_test` / `changeme`

## Build and Test

- Frontend build: `cd frontend && npm run build`
- Backend tests: `python -m pytest backend/tests -q`

## Notes

- Local development defaults to SQLite (`dev.db`).
- Set `SECRET_KEY` and `DATABASE_URL` through environment variables for non-local deployments.
