Backend (FastAPI) — Quickstart

Prerequisites
- Python 3.10+
- Recommended: virtualenv

Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Initialize DB (creates default users `maintainer`, `coordinator`, `teacher` with password `changeme`)

```bash
python backend/init_db.py
```

Run server (development)

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Notes
- By default the backend uses SQLite (`sqlite:///./dev.db`) for local development. Set `DATABASE_URL` to a Postgres URL in production.
- Secrets: set `SECRET_KEY` in environment for JWT signing.
