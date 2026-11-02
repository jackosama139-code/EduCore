from datetime import datetime, timedelta, timezone

from tests.conftest import auth, enroll


def future(days=7):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def new_assignment(client, who, course_id, due=None, max_marks=50):
    return client.post(f"/api/v1/courses/{course_id}/assignments",
                       json={"title": "Lab 1", "due_date": due or future(), "max_marks": max_marks}, headers=auth(who))


def test_faculty_creates_assignment_students_cannot(client, faculty, faculty2, stu1, course):
    assert new_assignment(client, faculty, course["id"]).status_code == 201
    assert new_assignment(client, faculty2, course["id"]).status_code == 403
    assert new_assignment(client, stu1[0], course["id"]).status_code == 403
    assert client.post(f"/api/v1/courses/{course['id']}/assignments", json={"title": "", "due_date": future()}, headers=auth(faculty)).status_code == 422
    assert new_assignment(client, faculty, 9999).status_code == 404


def test_only_enrolled_students_can_view_and_submit(client, faculty, stu1, stu2, course):
    enroll(client, faculty, course["id"], stu1[1])
    a = new_assignment(client, faculty, course["id"]).json()
    assert client.get(f"/api/v1/courses/{course['id']}/assignments", headers=auth(stu1[0])).json()["total"] == 1
    assert client.get(f"/api/v1/courses/{course['id']}/assignments", headers=auth(stu2[0])).status_code == 403
    assert client.get(f"/api/v1/assignments/{a['id']}", headers=auth(stu2[0])).status_code == 403
    assert client.post(f"/api/v1/assignments/{a['id']}/submissions", json={"content": "x"}, headers=auth(stu2[0])).status_code == 403


def test_submit_once_and_late_detection(client, faculty, stu1, course):
    enroll(client, faculty, course["id"], stu1[1])
    on_time = new_assignment(client, faculty, course["id"]).json()
    late = new_assignment(client, faculty, course["id"], due=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()).json()
    r = client.post(f"/api/v1/assignments/{on_time['id']}/submissions", json={"content": "my answer"}, headers=auth(stu1[0]))
    assert r.status_code == 201 and r.json()["is_late"] is False and r.json()["marks"] is None
    assert client.post(f"/api/v1/assignments/{on_time['id']}/submissions", json={"content": "again"}, headers=auth(stu1[0])).status_code == 409
    assert client.post(f"/api/v1/assignments/{late['id']}/submissions", json={"content": "oops"}, headers=auth(stu1[0])).json()["is_late"] is True
    assert client.post(f"/api/v1/assignments/{late['id']}/submissions", json={"content": ""}, headers=auth(stu1[0])).status_code in (409, 422)


def test_faculty_views_submissions_and_grades(client, faculty, faculty2, stu1, stu2, course):
    for _, p in (stu1, stu2):
        enroll(client, faculty, course["id"], p)
    a = new_assignment(client, faculty, course["id"], max_marks=50).json()
    subs = [client.post(f"/api/v1/assignments/{a['id']}/submissions", json={"content": f"ans {i}"}, headers=auth(u)).json()
            for i, (u, _) in enumerate((stu1, stu2))]
    listing = client.get(f"/api/v1/assignments/{a['id']}/submissions", headers=auth(faculty)).json()
    assert listing["total"] == 2
    assert client.get(f"/api/v1/assignments/{a['id']}/submissions", headers=auth(faculty2)).status_code == 403
    assert client.get(f"/api/v1/assignments/{a['id']}/submissions", headers=auth(stu1[0])).status_code == 403

    sid = subs[0]["id"]
    assert client.put(f"/api/v1/submissions/{sid}/grade", json={"marks": 60}, headers=auth(faculty)).status_code == 400  # > max
    assert client.put(f"/api/v1/submissions/{sid}/grade", json={"marks": -1}, headers=auth(faculty)).status_code == 422
    assert client.put(f"/api/v1/submissions/{sid}/grade", json={"marks": 45, "feedback": "Good"}, headers=auth(faculty2)).status_code == 403
    g = client.put(f"/api/v1/submissions/{sid}/grade", json={"marks": 45, "feedback": "Good"}, headers=auth(faculty))
    assert g.status_code == 200 and g.json()["marks"] == 45


def test_student_sees_only_own_submissions(client, faculty, stu1, stu2, course):
    for _, p in (stu1, stu2):
        enroll(client, faculty, course["id"], p)
    a = new_assignment(client, faculty, course["id"]).json()
    for u, _ in (stu1, stu2):
        client.post(f"/api/v1/assignments/{a['id']}/submissions", json={"content": "mine"}, headers=auth(u))
    mine = client.get("/api/v1/submissions/me", headers=auth(stu1[0])).json()
    assert mine["total"] == 1 and mine["items"][0]["student_id"] == stu1[1].id
