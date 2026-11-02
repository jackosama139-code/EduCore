from tests.conftest import auth, enroll


def test_faculty_creates_course_for_self(client, faculty, course):
    assert course["code"] == "CS101" and course["faculty_id"] == faculty.id and course["faculty_name"] == "Prof One"


def test_student_cannot_create_course(client, stu1):
    r = client.post("/api/v1/courses", json={"code": "X1", "title": "T"}, headers=auth(stu1[0]))
    assert r.status_code == 403


def test_duplicate_code_conflict_and_validation(client, faculty, course):
    assert client.post("/api/v1/courses", json={"code": "CS101", "title": "Dup"}, headers=auth(faculty)).status_code == 409
    assert client.post("/api/v1/courses", json={"code": "CS102", "title": "T", "credits": 99}, headers=auth(faculty)).status_code == 422


def test_admin_must_name_faculty_and_can_manage_any_course(client, admin, faculty, course):
    assert client.post("/api/v1/courses", json={"code": "A1", "title": "T"}, headers=auth(admin)).status_code == 400
    r = client.post("/api/v1/courses", json={"code": "A1", "title": "T", "faculty_id": faculty.id}, headers=auth(admin))
    assert r.status_code == 201
    assert client.put(f"/api/v1/courses/{course['id']}", json={"title": "Renamed"}, headers=auth(admin)).json()["title"] == "Renamed"
    assert client.get("/api/v1/courses", headers=auth(admin)).json()["total"] == 2


def test_faculty_cannot_modify_someone_elses_course(client, faculty2, course):
    assert client.put(f"/api/v1/courses/{course['id']}", json={"title": "Hacked"}, headers=auth(faculty2)).status_code == 403
    assert client.delete(f"/api/v1/courses/{course['id']}", headers=auth(faculty2)).status_code == 403
    assert client.get("/api/v1/courses", headers=auth(faculty2)).json()["total"] == 0


def test_enrollment_rules(client, faculty, faculty2, stu1, course):
    assert enroll(client, faculty, course["id"], stu1[1]).status_code == 201
    assert enroll(client, faculty, course["id"], stu1[1]).status_code == 409          # duplicate
    assert enroll(client, faculty2, course["id"], stu1[1]).status_code == 403          # not their course
    assert client.post(f"/api/v1/courses/{course['id']}/enrollments", json={"student_id": 999}, headers=auth(faculty)).status_code == 404
    assert client.post(f"/api/v1/courses/{course['id']}/enrollments", json={"student_id": stu1[1].id}, headers=auth(stu1[0])).status_code == 403


def test_student_sees_only_enrolled_courses(client, faculty, stu1, stu2, course):
    client.post("/api/v1/courses", json={"code": "CS202", "title": "Other"}, headers=auth(faculty))
    enroll(client, faculty, course["id"], stu1[1])
    mine = client.get("/api/v1/courses", headers=auth(stu1[0])).json()
    assert [c["code"] for c in mine["items"]] == ["CS101"]
    assert client.get("/api/v1/students/me/courses", headers=auth(stu1[0])).json()["total"] == 1
    assert client.get(f"/api/v1/courses/{course['id']}", headers=auth(stu1[0])).status_code == 200
    assert client.get(f"/api/v1/courses/{course['id']}", headers=auth(stu2[0])).status_code == 403
    assert client.get("/api/v1/courses", headers=auth(stu2[0])).json()["total"] == 0


def test_unenroll_and_delete_course(client, faculty, stu1, course):
    enroll(client, faculty, course["id"], stu1[1])
    assert client.get(f"/api/v1/courses/{course['id']}/students", headers=auth(faculty)).json()["total"] == 1
    assert client.delete(f"/api/v1/courses/{course['id']}/enrollments/{stu1[1].id}", headers=auth(faculty)).status_code == 204
    assert client.delete(f"/api/v1/courses/{course['id']}/enrollments/{stu1[1].id}", headers=auth(faculty)).status_code == 404
    assert client.delete(f"/api/v1/courses/{course['id']}", headers=auth(faculty)).status_code == 204
    assert client.get(f"/api/v1/courses/{course['id']}", headers=auth(faculty)).status_code == 404


def test_cannot_enroll_in_inactive_course(client, faculty, stu1, course):
    client.put(f"/api/v1/courses/{course['id']}", json={"is_active": False}, headers=auth(faculty))
    assert enroll(client, faculty, course["id"], stu1[1]).status_code == 400
