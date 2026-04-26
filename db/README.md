# Database Folder

This folder contains SQL artifacts for database setup and reference.

## Files

- `schema.sql` - Canonical SQL schema for core entities (users, students, subjects, timetable, letters, attendance, logs).

## Usage

- Use this schema as the source of truth for relational structure review.
- For local development setup, prefer the backend bootstrap command:
  - `python backend/init_db.py`

## Notes

- The runtime app currently uses ORM models under `backend/app/models.py` and local SQLite by default.
