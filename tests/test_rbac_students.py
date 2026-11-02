from tests.conftest import auth, enroll


def test_only_admin_creates_users_with_roles(client, admin, faculty, stu1):
    payload = {"email": "newfac@test.edu", "full_name": "NF", "password": "Passw0rd123", "role": "faculty"}
    assert client.post("/api/v1/users", json=payload, headers=auth(admin)).status_code == 201
    assert client.post("/api/v1/users", json=payload, headers=auth(faculty)).status_code == 403
    assert client.post("/api/v1/users", json=payload, headers=auth(stu1[0])).status_code == 403


def test_admin_creates_student_profile_with_validation(client, admin, db):
    from tests.conftest import make_user
    from app.models import Role
    u = make_user(db, Role.student, "p@test.edu")
    body = {"user_id": u.id, "roll_number": "CS-001", "department": "CSE", "semester": 3}
    r = client.post("/api/v1/students", json=body, headers=auth(admin))
    assert r.status_code == 201 and r.json()["full_name"] == "Test User"
    assert client.post("/api/v1/students", json=body, headers=auth(admin)).status_code == 409  # one profile per user
    assert client.post("/api/v1/students", json={**body, "semester": 12}, headers=auth(admin)).status_code == 422


def test_cannot_create_profile_for_faculty_user(client, admin, faculty):
    r = client.post("/api/v1/students", json={"user_id": faculty.id, "roll_number": "X1", "department": "CSE"}, headers=auth(admin))
    assert r.status_code == 400


def test_student_sees_own_profile_not_others(client, stu1, stu2):
    (u1, p1), (u2, p2) = stu1, stu2
    assert client.get("/api/v1/students/me", headers=auth(u1)).json()["id"] == p1.id
    assert client.get(f"/api/v1/students/{p1.id}", headers=auth(u1)).status_code == 200
    # IDOR attempt: student 1 asks for student 2's record
    assert client.get(f"/api/v1/students/{p2.id}", headers=auth(u1)).status_code == 404


def test_student_cannot_list_students_or_edit_protected_fields(client, stu1):
    u1, p1 = stu1
    assert client.get("/api/v1/students", headers=auth(u1)).status_code == 403
    assert client.put(f"/api/v1/students/{p1.id}", json={"semester": 8}, headers=auth(u1)).status_code == 403
    # self-update only touches phone / dob; 'semester' in body is ignored
    r = client.put("/api/v1/students/me", json={"phone": "9999999999", "semester": 8}, headers=auth(u1))
    assert r.status_code == 200 and r.json()["phone"] == "9999999999" and r.json()["semester"] == 5


def test_admin_updates_and_paginates_students(client, admin, db):
    from tests.conftest import make_student
    for i in range(1, 6):
        make_student(db, i)
    r = client.get("/api/v1/students?page=2&size=2", headers=auth(admin)).json()
    assert r["total"] == 5 and r["pages"] == 3 and len(r["items"]) == 2 and r["page"] == 2
    assert client.get("/api/v1/students?size=1000", headers=auth(admin)).status_code == 422
    s = client.get("/api/v1/students?search=R003", headers=auth(admin)).json()
    assert s["total"] == 1
    sid = s["items"][0]["id"]
    assert client.put(f"/api/v1/students/{sid}", json={"semester": 6}, headers=auth(admin)).json()["semester"] == 6
    assert client.put(f"/api/v1/students/{sid}", json={"roll_number": "R001"}, headers=auth(admin)).status_code == 409


def test_faculty_only_sees_students_in_their_courses(client, faculty, faculty2, stu1, stu2, course):
    enroll(client, faculty, course["id"], stu1[1])
    ids = [s["id"] for s in client.get("/api/v1/students", headers=auth(faculty)).json()["items"]]
    assert ids == [stu1[1].id]
    assert client.get(f"/api/v1/students/{stu2[1].id}", headers=auth(faculty)).status_code == 403
    assert client.get("/api/v1/students", headers=auth(faculty2)).json()["total"] == 0
