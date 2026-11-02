# EduCore — Interview Guide (based on the actual code)

## 30-second pitch
"EduCore is a role-based College ERP/LMS backend in FastAPI + PostgreSQL. It has JWT auth with admin/faculty/student roles, course and enrollment management, attendance with percentage calculation, assignments with submission and grading, and dashboards. It's layered — routes, services, models, schemas — authorization lives in one module, integrity is enforced by DB constraints, and it's covered by 50 pytest tests. There's also an optional RAG-style PDF assistant that runs without any LLM key."

## How one request flows (trace `GET /api/v1/attendance/me/summary`)
1. `oauth2_scheme` extracts the Bearer token → `get_current_user` decodes JWT (`core/security.py`), loads the user from DB, checks `is_active`.
2. `require_roles(Role.student)` checks the role → else 403.
3. Route (`api/routes/attendance.py`) finds the caller's *own* student profile — the id never comes from the client.
4. `attendance_service.student_summary` runs ONE grouped SQL query (enrollments → courses LEFT JOIN attendance, `COUNT` + `SUM(CASE…)`).
5. Result is validated/serialised through the `AttendanceSummary` Pydantic model.

## Questions & model answers

### Auth & security
1. **Why bcrypt and not SHA-256?** SHA is fast, so brute force is cheap. bcrypt is deliberately slow, salted per hash (two identical passwords give different hashes — see `test_password_hashing_is_salted…`) and has a tunable cost.
2. **What's inside your JWT? Is it encrypted?** `sub` (user id), `role`, `iat`, `exp`, signed HS256. Signed, not encrypted — anyone can read it, nobody can forge it. So no secrets inside.
3. **Why re-read the role from the DB instead of trusting the token's role claim?** A token lives up to 60 minutes; if an admin deactivates or demotes someone, the token would still say the old role. DB lookup costs one indexed query and makes changes immediate (`test_disabled_account_…`).
4. **How do you stop a student registering as admin?** `/auth/register` doesn't accept a role (extra JSON field is ignored; role is hard-coded to student). Admin/faculty accounts are made via admin-only `POST /users`. Test: `test_register_cannot_choose_admin_role`.
5. **What is IDOR and where did you prevent it?** Insecure Direct Object Reference: changing `/students/5` to `/students/6`. `access.assert_can_view_student` checks ownership; "my data" endpoints use `/me` and derive the id from the token. Students get **404** not 403 for others' records so existence isn't leaked.
6. **Why the same error for wrong password and unknown email?** Prevents account enumeration.
7. **Token revocation/logout?** Not implemented (stateless JWT). Options: short expiry + refresh tokens, a denylist table/Redis keyed by `jti`. I'd mention this honestly as a known limitation.
8. **Where do secrets live?** Environment/.env via `pydantic-settings`; `SECRET_KEY` and `DATABASE_URL` have no defaults, so the app won't boot without them.

### FastAPI & Pydantic
9. **What is `Depends` and how is it used here?** Dependency injection: `get_db` (session per request, closed in `finally`), `get_current_user`, `require_roles(...)` (a factory returning a dependency), `PageParams`.
10. **Pydantic schema vs SQLAlchemy model?** Model = DB table; schema = API contract/validation. Separate so we never leak `hashed_password` and clients can't set fields like `role` or `is_active`. `from_attributes=True` lets Pydantic read ORM objects.
11. **Why is `/students/me` declared before `/students/{student_id}`?** Routes match in order; otherwise `"me"` would be parsed as an int id → 422.
12. **sync `def` vs `async def` endpoints?** I use sync `def` with a sync SQLAlchemy driver; FastAPI runs them in a threadpool so the event loop isn't blocked. `async def` with a blocking DB call would block everything. Switching to async needs `asyncpg` + `AsyncSession`.
13. **How are errors handled?** Services raise `AppError` subclasses; a single exception handler returns `{"detail": …}` with the right status. Validation errors are automatic 422s. Business code doesn't import FastAPI.

### Database design
14. **Walk through the schema.** users 1—1 student_profiles; users(faculty) 1—N courses; students N—M courses via `enrollments`; attendance_records and submissions reference student + course/assignment. Cascades: deleting a course removes its enrollments/assignments; `RESTRICT` stops deleting a faculty who owns courses.
15. **Which constraints protect data integrity?** `uq_enrollment_student_course`, `uq_attendance_day (course, student, date)`, `uq_submission_once`, CHECKs on semester/credits/max_marks. Code checks give friendly errors; constraints guarantee correctness under race conditions — I also catch `IntegrityError` and convert it to 409.
16. **Why store enums as VARCHAR + CHECK, not PG ENUM?** Altering native enums in migrations is painful and DB-specific; this is portable (tests run on SQLite).
17. **N+1 queries — where did you avoid them?** `joinedload(StudentProfile.user)` / `joinedload(Course.faculty)` because response schemas read `full_name`/`faculty_name`. Attendance summary is one grouped query instead of one per course.
18. **Explain pagination.** `LIMIT/OFFSET` plus a `COUNT(*)` over the same filtered query (`services/pagination.py`). Response has `total/page/size/pages`; size capped at 100. Trade-off: large OFFSETs get slow → keyset pagination for huge tables.
19. **Why Alembic and not `create_all`?** Versioned, reviewable, reversible schema changes in production. I verified upgrade → downgrade → upgrade and `alembic check` (no drift) on PostgreSQL.
20. **Datetime pitfall you handled?** SQLite returns naive datetimes, PostgreSQL aware ones; `as_utc()` normalises before the late-submission comparison.

### Business logic
21. **How is attendance % computed?** (present + late)/total × 100, rounded to 2 dp; `None` when no classes yet (avoids divide-by-zero and "0%" lying). Flag `below_threshold` uses configurable 75%.
22. **Why is marking attendance an upsert?** Teachers correct mistakes; re-posting the same day updates rows instead of failing on the unique constraint.
23. **How do you validate the attendance request?** Pydantic: non-empty list, enum status, no duplicate student ids; service: not future-dated, every student actually enrolled in that course, caller manages the course.
24. **Faculty visibility rule?** Faculty only see students enrolled in *their* courses (subquery on enrollments→courses); attendance summary for faculty is filtered to their own courses so they can't see attendance in other teachers' classes.

### Testing & ops
25. **How do you test?** Pytest + FastAPI `TestClient`, `dependency_overrides[get_db]` swapping in in-memory SQLite (StaticPool), schema created/dropped per test. Tests cover happy paths *and* authorization (IDOR, wrong role, other faculty), validation, duplicates, pagination, percentages.
26. **SQLite in tests vs PostgreSQL in prod — risk?** Dialect differences can hide bugs. I mitigated by running the migrations, seed and live API against real PostgreSQL; in a team setting I'd run tests on a Postgres container in CI.
27. **Docker setup?** Compose has `db` (healthcheck) and `api` (`depends_on: service_healthy`); API container runs `alembic upgrade head` then uvicorn, as a non-root user; DB host is the service name `db`.

### AI module
28. **Explain RAG as you built it.** Extract PDF text → split into overlapping 150-word chunks → store → at question time rank chunks with BM25 → send top-k as context to the LLM with an instruction to answer only from them. Overlap prevents losing sentences at chunk edges.
29. **Why BM25 and not embeddings?** No external service/model, deterministic, testable, fine for a few documents. Upgrade: embeddings + pgvector; hybrid search.
30. **Failure & safety design?** Optional by flag (`AI_ENABLED`), lazy `anthropic` import, no key → extractive mode, LLM error → fallback, 10 MB cap, `%PDF` magic-byte check, per-owner isolation, prompt tells the model the excerpts are untrusted (prompt-injection defence).

## "What would you improve?" (have this ready)
Refresh tokens/logout denylist · login rate limiting · async stack · audit log · soft deletes · Postgres in CI · caching dashboard queries · keyset pagination · background worker for PDF ingestion · embeddings/pgvector.

## Likely live-coding asks (you can do these from this codebase)
Add a `GET /courses/{id}/attendance-report` endpoint · add `PATCH` for assignments · add a unique `roll_number` format validator · add a `/students/me/grades` endpoint · write a test for a new rule.
