"""Test setup. Env vars are set BEFORE importing the app so no real secrets/DB are needed.
Tests run on in-memory SQLite; production uses PostgreSQL (same SQLAlchemy code)."""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-1234567890"
os.environ["AI_ENABLED"] = "true"
os.environ["ANTHROPIC_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, StudentProfile, User  # noqa: E402

PASSWORD = "Passw0rd123"
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    s = TestingSession()
    yield s
    s.close()


@pytest.fixture
def client(db):
    def override():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---- factories ------------------------------------------------------------
def make_user(db, role: Role, email: str, name: str = "Test User") -> User:
    u = User(email=email, full_name=name, hashed_password=hash_password(PASSWORD), role=role)
    db.add(u)
    db.commit()
    return u


def make_student(db, n: int = 1) -> tuple[User, StudentProfile]:
    u = make_user(db, Role.student, f"student{n}@test.edu", f"Student {n}")
    p = StudentProfile(user_id=u.id, roll_number=f"R{n:03d}", department="CSE", semester=5)
    db.add(p)
    db.commit()
    return u, p


def auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


@pytest.fixture
def admin(db):
    return make_user(db, Role.admin, "admin@test.edu", "Admin")


@pytest.fixture
def faculty(db):
    return make_user(db, Role.faculty, "faculty1@test.edu", "Prof One")


@pytest.fixture
def faculty2(db):
    return make_user(db, Role.faculty, "faculty2@test.edu", "Prof Two")


@pytest.fixture
def stu1(db):
    return make_student(db, 1)


@pytest.fixture
def stu2(db):
    return make_student(db, 2)


@pytest.fixture
def course(client, faculty):
    r = client.post("/api/v1/courses", json={"code": "cs101", "title": "Intro to CS", "credits": 4}, headers=auth(faculty))
    assert r.status_code == 201, r.text
    return r.json()


def enroll(client, who, course_id, student_profile):
    return client.post(f"/api/v1/courses/{course_id}/enrollments", json={"student_id": student_profile.id}, headers=auth(who))
