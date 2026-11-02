# EduCore — College ERP & Learning Management System (backend)

A modular, role-based REST backend built with **FastAPI, PostgreSQL, SQLAlchemy 2.0, Pydantic v2, JWT, Alembic, Pytest and Docker**.
Roles: **admin**, **faculty**, **student**. No frontend — use the Swagger UI at `/docs`.

## Features
| Area | What it does |
|---|---|
| Auth | Register, login (OAuth2 password flow), bcrypt hashing, JWT access tokens, role-based access control |
| Students | Admin creates/updates profiles; students view/edit only their own (contact details only) |
| Courses | Faculty manage their own courses, admin manages all; enrollment; students see only enrolled courses |
| Attendance | Faculty mark attendance (idempotent per day), students view own records, % calculation + low-attendance flag |
| Assignments | Faculty create, students submit once (late detection), faculty view submissions and grade |
| Dashboards | Separate admin / faculty / student dashboards (counts, attendance stats, assignment summaries) |
| AI assistant *(optional)* | Upload PDF notes, ask questions (BM25 retrieval + optional LLM). Off by default |

## Architecture
```
Request ─► api/routes  ─► services ─► models (SQLAlchemy) ─► PostgreSQL
            (HTTP only)   (business     (tables, FKs,
             deps.py       rules +       constraints)
             = auth        authorization)
            schemas = Pydantic request/response validation
```
```
app/
  main.py              app factory, router wiring, /health, optional AI module switch
  core/                config.py (env vars), security.py (bcrypt + JWT), exceptions.py
  db/                  base.py (Declarative base), session.py (engine + get_db dependency)
  models/              users, student_profiles, courses, enrollments, attendance_records,
                       assignments, submissions, documents(+chunks, AI only)
  schemas/             Pydantic models: validation + what is exposed in responses
  services/            ALL business logic. access.py holds every authorization rule
  api/deps.py          get_current_user, require_roles(...)
  api/routes/          thin controllers: parse request -> call service -> return
  ai/                  OPTIONAL module: retrieval.py (BM25), llm.py, service.py, router.py
alembic/               migrations        scripts/seed.py   demo data        tests/   pytest suite
```
**Key design decisions**
- *Routes are thin, services are thick.* Services raise domain exceptions (`NotFoundError`, `ForbiddenError`…); one handler maps them to HTTP status codes.
- *Authorization is centralised* in `services/access.py`. Student ids are **never taken from the URL** for "my data" endpoints (`/attendance/me/...`), and cross-student lookups return **404** (no existence leak).
- *Role is re-read from the DB on every request*, not trusted from the JWT, so deactivation / demotion applies instantly.
- *Public registration always creates a student.* Faculty/admin accounts are created by an admin (`POST /users`).
- *Integrity is enforced in the database*: unique constraints (one enrollment, one attendance row per day, one submission), CHECK constraints (semester 1-8, credits 1-10), foreign keys with explicit `ON DELETE` rules.
- *Attendance %* = (present + late) / total classes × 100. Threshold (default 75) is configurable.
- *AI module* lives in `app/ai/`, is imported only if `AI_ENABLED=true`, and works without any API key (returns the best-matching passages).

## Setup

### Option A — Docker (easiest, works on Windows with Docker Desktop)
```powershell
Copy-Item .env.example .env        # then edit .env: set passwords + SECRET_KEY
docker compose up --build          # starts PostgreSQL, runs migrations, starts the API
docker compose exec api python -m scripts.seed     # demo data (in a second terminal)
```
Open http://localhost:8000/docs

### Option B — Local Python + local PostgreSQL (Windows / PowerShell)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1       # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
Copy-Item .env.example .env        # edit it (see below)
# create the database (psql comes with the PostgreSQL installer):
psql -U postgres -c "CREATE USER educore WITH PASSWORD 'your_password'"
psql -U postgres -c "CREATE DATABASE educore OWNER educore"
alembic upgrade head               # create tables
python -m scripts.seed             # demo data
uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs
```
`.env` essentials: `DATABASE_URL=postgresql+psycopg2://educore:your_password@localhost:5432/educore`,
`SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">`, `SEED_DEFAULT_PASSWORD=<demo password>`.
(Special characters in the DB password must be URL-encoded, e.g. `@` → `%40`.)

### Tests (no PostgreSQL or .env required — they use in-memory SQLite)
```powershell
python -m pytest -q
```

### Demo accounts (after seeding; password = `SEED_DEFAULT_PASSWORD`)
`admin@educore.edu`, `anita.deshmukh@educore.edu` (faculty), `student01@educore.edu` … `student30@educore.edu`

## API reference (prefix `/api/v1`; all list endpoints take `?page=1&size=20`, max size 100)
| Method & path | Who | Purpose |
|---|---|---|
| POST `/auth/register` | public | Self-register (always a student) |
| POST `/auth/login` | public | Form fields `username`(email), `password` → JWT |
| GET `/auth/me` | any | Current user |
| POST `/users` · GET `/users` · PATCH `/users/{id}/status` | admin | Create any-role user, list, activate/deactivate |
| POST `/students` | admin | Create student profile for a student user |
| GET `/students` | admin, faculty* | List (`department`, `search`); *faculty see only their own students |
| GET `/students/me` · PUT `/students/me` | student | Own profile / edit phone, DOB |
| GET `/students/me/courses` | student | Enrolled courses |
| GET `/students/{id}` | admin, faculty*, student (own only) | One profile |
| PUT `/students/{id}` | admin | Update any field |
| POST `/courses` | faculty, admin | Create (faculty → own; admin must pass `faculty_id`) |
| GET `/courses` | any | Role-aware: admin all, faculty own, student enrolled |
| GET/PUT/DELETE `/courses/{id}` | view: owner/admin/enrolled · edit: owner/admin | |
| POST `/courses/{id}/enrollments` · DELETE `/courses/{id}/enrollments/{student_id}` | course owner, admin | Enroll / remove |
| GET `/courses/{id}/students` | course owner, admin | Roster |
| POST `/attendance/courses/{id}` | course owner, admin | Mark/correct a day |
| GET `/attendance/courses/{id}?class_date=` | course owner, admin | Course attendance |
| GET `/attendance/me/summary` · `/attendance/me/records` | student | Own % per course + overall, own records |
| GET `/attendance/students/{id}/summary` | admin, faculty* | A student's summary |
| POST/GET `/courses/{id}/assignments` | create: owner/admin · list: owner/admin/enrolled | |
| GET/DELETE `/assignments/{id}` | | |
| POST `/assignments/{id}/submissions` | enrolled student | Submit once |
| GET `/assignments/{id}/submissions` | course owner, admin | View submissions |
| GET `/submissions/me` | student | Own submissions |
| PUT `/submissions/{id}/grade` | course owner, admin | `marks` ≤ `max_marks` |
| GET `/dashboard/admin` · `/faculty` · `/student` | matching role | Stats |
| POST `/assistant/documents` · GET · DELETE `/{id}` · POST `/{id}/ask` | student (AI enabled) | PDF notes Q&A |
| GET `/health` | public | DB connectivity |

Status codes: 200/201/204 success · 400 business-rule violation · 401 bad/missing token · 403 role/ownership · 404 not found · 409 duplicate · 422 validation.

## Sample requests
```bash
# 1. log in (form-encoded)
curl -X POST localhost:8000/api/v1/auth/login -d "username=student01@educore.edu&password=<SEED_DEFAULT_PASSWORD>"
# 2. use the token
TOKEN=eyJ...
curl localhost:8000/api/v1/attendance/me/summary -H "Authorization: Bearer $TOKEN"

# faculty marks attendance
curl -X POST localhost:8000/api/v1/attendance/courses/1 -H "Authorization: Bearer $FACULTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"class_date":"2026-10-30","records":[{"student_id":1,"status":"present"},{"student_id":2,"status":"late"}]}'

# faculty creates an assignment
curl -X POST localhost:8000/api/v1/courses/1/assignments -H "Authorization: Bearer $FACULTY_TOKEN" \
  -H "Content-Type: application/json" -d '{"title":"Lab 4","due_date":"2026-11-15T18:00:00Z","max_marks":50}'

# student submits
curl -X POST localhost:8000/api/v1/assignments/1/submissions -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"content":"My solution..."}'
```
Example response of `GET /attendance/me/summary`:
```json
{"student_id":1,"overall_percentage":95.31,"threshold":75.0,
 "courses":[{"course_id":1,"course_code":"CS201","course_title":"Data Structures & Algorithms",
             "total_classes":16,"attended":14,"percentage":87.5,"below_threshold":false}]}
```

## Optional AI learning assistant
Set `AI_ENABLED=true` and restart. Without `ANTHROPIC_API_KEY` answers are **extractive** (best matching passages, `"mode":"extractive"`).
With a key, the top passages are sent to the LLM (`"mode":"llm"`); if the LLM call fails it falls back to extractive.
Pipeline: PDF → `pypdf` text → 150-word overlapping chunks (stored in Postgres) → BM25 ranking → (optional) LLM answer grounded in those chunks.
Limits: text PDFs only (no OCR), 10 MB upload cap, documents are private to their owner.

## Security notes
No secrets in code (`.env` is git-ignored; app refuses to start without `SECRET_KEY` ≥ 32 chars) · bcrypt hashes · identical login error for unknown user / wrong password · parameterised queries via SQLAlchemy · request size/pagination caps · LLM prompt treats PDF text as untrusted data.
**Production TODO (deliberately out of scope):** HTTPS/reverse proxy, login rate-limiting, refresh tokens, audit logging, CORS config if a browser frontend is added.
