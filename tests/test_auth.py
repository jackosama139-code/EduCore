from app.core.security import create_access_token, hash_password, verify_password
from tests.conftest import PASSWORD, auth, make_user
from app.models import Role

URL = "/api/v1/auth"


def test_password_hashing_is_salted_and_verifiable():
    h1, h2 = hash_password("Secret123"), hash_password("Secret123")
    assert h1 != h2 and h1 != "Secret123"
    assert verify_password("Secret123", h1) and not verify_password("wrong", h1)


def test_register_creates_student_and_never_returns_password(client):
    r = client.post(f"{URL}/register", json={"email": "New@Test.edu", "full_name": "New", "password": PASSWORD})
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "student" and body["email"] == "new@test.edu"
    assert "password" not in body and "hashed_password" not in body


def test_register_cannot_choose_admin_role(client):
    r = client.post(f"{URL}/register", json={"email": "evil@test.edu", "full_name": "Evil", "password": PASSWORD, "role": "admin"})
    assert r.status_code == 201 and r.json()["role"] == "student"


def test_register_duplicate_email_conflict(client):
    payload = {"email": "dup@test.edu", "full_name": "D", "password": PASSWORD}
    assert client.post(f"{URL}/register", json=payload).status_code == 201
    assert client.post(f"{URL}/register", json=payload).status_code == 409


def test_register_validation(client):
    bad_pw = client.post(f"{URL}/register", json={"email": "a@test.edu", "full_name": "A", "password": "short"})
    no_digit = client.post(f"{URL}/register", json={"email": "a@test.edu", "full_name": "A", "password": "onlyletters"})
    bad_email = client.post(f"{URL}/register", json={"email": "nope", "full_name": "A", "password": PASSWORD})
    assert bad_pw.status_code == no_digit.status_code == bad_email.status_code == 422


def test_login_success_and_me(client, db):
    make_user(db, Role.faculty, "f@test.edu")
    r = client.post(f"{URL}/login", data={"username": "f@test.edu", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"
    me = client.get(f"{URL}/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200 and me.json()["role"] == "faculty"


def test_login_wrong_password_and_unknown_user_look_identical(client, db):
    make_user(db, Role.student, "s@test.edu")
    a = client.post(f"{URL}/login", data={"username": "s@test.edu", "password": "WrongPass1"})
    b = client.post(f"{URL}/login", data={"username": "ghost@test.edu", "password": "WrongPass1"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_protected_route_requires_valid_token(client):
    assert client.get(f"{URL}/me").status_code == 401
    assert client.get(f"{URL}/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_expired_token_rejected(client, db):
    u = make_user(db, Role.student, "s@test.edu")
    expired = create_access_token(u.id, "student", expires_minutes=-5)
    assert client.get(f"{URL}/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_disabled_account_cannot_login_or_use_old_token(client, db, admin):
    u = make_user(db, Role.student, "s@test.edu")
    headers = auth(u)
    r = client.patch(f"/api/v1/users/{u.id}/status", json={"is_active": False}, headers=auth(admin))
    assert r.status_code == 200
    assert client.post(f"{URL}/login", data={"username": "s@test.edu", "password": PASSWORD}).status_code == 403
    assert client.get(f"{URL}/me", headers=headers).status_code == 403
