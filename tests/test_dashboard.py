from datetime import date, datetime, timedelta, timezone

from tests.conftest import auth, enroll


def test_dashboards(client, admin, faculty, stu1, stu2, course):
    for _, p in (stu1, stu2):
        enroll(client, faculty, course["id"], p)
    d = date.today() - timedelta(days=1)
    client.post(f"/api/v1/attendance/courses/{course['id']}", headers=auth(faculty), json={
        "class_date": d.isoformat(),
        "records": [{"student_id": stu1[1].id, "status": "present"}, {"student_id": stu2[1].id, "status": "absent"}]})
    soon = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    a1 = client.post(f"/api/v1/courses/{course['id']}/assignments", json={"title": "A1", "due_date": soon, "max_marks": 100}, headers=auth(faculty)).json()
    client.post(f"/api/v1/courses/{course['id']}/assignments", json={"title": "A2", "due_date": past, "max_marks": 100}, headers=auth(faculty))
    sub = client.post(f"/api/v1/assignments/{a1['id']}/submissions", json={"content": "x"}, headers=auth(stu1[0])).json()
    client.put(f"/api/v1/submissions/{sub['id']}/grade", json={"marks": 80}, headers=auth(faculty))

    a = client.get("/api/v1/dashboard/admin", headers=auth(admin)).json()
    assert (a["student_count"], a["faculty_count"], a["course_count"], a["enrollment_count"]) == (2, 1, 1, 2)
    assert a["attendance"]["overall_percentage"] == 50.0
    assert a["assignments"]["total_assignments"] == 2 and a["assignments"]["graded_submissions"] == 1
    assert a["assignments"]["average_score_percent"] == 80.0

    f = client.get("/api/v1/dashboard/faculty", headers=auth(faculty)).json()
    assert f["course_count"] == 1 and f["student_count"] == 2

    s = client.get("/api/v1/dashboard/student", headers=auth(stu1[0])).json()
    assert s["enrolled_courses"] == 1 and s["attendance_percentage"] == 100.0
    assert s["assignments"] == {"total": 2, "submitted": 1, "pending": 0, "overdue": 1, "graded": 1, "average_score_percent": 80.0}


def test_dashboard_role_guards(client, admin, faculty, stu1):
    assert client.get("/api/v1/dashboard/admin", headers=auth(faculty)).status_code == 403
    assert client.get("/api/v1/dashboard/admin", headers=auth(stu1[0])).status_code == 403
    assert client.get("/api/v1/dashboard/student", headers=auth(admin)).status_code == 403
    assert client.get("/api/v1/dashboard/admin").status_code == 401
