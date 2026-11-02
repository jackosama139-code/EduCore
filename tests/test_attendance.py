from datetime import date, timedelta

from app.services.attendance_service import percentage
from tests.conftest import auth, enroll


def mark(client, who, course_id, day, records):
    return client.post(f"/api/v1/attendance/courses/{course_id}",
                       json={"class_date": day.isoformat(), "records": records}, headers=auth(who))


def test_percentage_function():
    assert percentage(3, 4) == 75.0 and percentage(1, 3) == 33.33 and percentage(0, 0) is None


def test_mark_and_compute_percentage(client, faculty, stu1, course):
    u, p = stu1
    enroll(client, faculty, course["id"], p)
    today = date.today()
    statuses = ["present", "present", "late", "absent"]  # late counts as attended -> 3/4
    for i, st in enumerate(statuses):
        assert mark(client, faculty, course["id"], today - timedelta(days=i + 1), [{"student_id": p.id, "status": st}]).status_code == 200
    s = client.get("/api/v1/attendance/me/summary", headers=auth(u)).json()
    assert s["overall_percentage"] == 75.0
    c = s["courses"][0]
    assert (c["total_classes"], c["attended"], c["percentage"], c["below_threshold"]) == (4, 3, 75.0, False)


def test_below_threshold_flag(client, faculty, stu1, course):
    u, p = stu1
    enroll(client, faculty, course["id"], p)
    for i, st in enumerate(["present", "absent", "absent"]):
        mark(client, faculty, course["id"], date.today() - timedelta(days=i + 1), [{"student_id": p.id, "status": st}])
    c = client.get("/api/v1/attendance/me/summary", headers=auth(u)).json()["courses"][0]
    assert c["percentage"] == 33.33 and c["below_threshold"] is True


def test_remarking_same_day_updates_instead_of_duplicating(client, faculty, stu1, course):
    u, p = stu1
    enroll(client, faculty, course["id"], p)
    d = date.today() - timedelta(days=1)
    mark(client, faculty, course["id"], d, [{"student_id": p.id, "status": "absent"}])
    mark(client, faculty, course["id"], d, [{"student_id": p.id, "status": "present"}])
    recs = client.get("/api/v1/attendance/me/records", headers=auth(u)).json()
    assert recs["total"] == 1 and recs["items"][0]["status"] == "present"


def test_attendance_validation_rules(client, faculty, faculty2, stu1, stu2, course):
    _, p1 = stu1
    enroll(client, faculty, course["id"], p1)
    d = date.today() - timedelta(days=1)
    assert mark(client, faculty, course["id"], date.today() + timedelta(days=1), [{"student_id": p1.id, "status": "present"}]).status_code == 400
    assert mark(client, faculty, course["id"], d, [{"student_id": stu2[1].id, "status": "present"}]).status_code == 400  # not enrolled
    assert mark(client, faculty2, course["id"], d, [{"student_id": p1.id, "status": "present"}]).status_code == 403    # not their course
    assert mark(client, stu1[0], course["id"], d, [{"student_id": p1.id, "status": "present"}]).status_code == 403     # student
    assert mark(client, faculty, course["id"], d, [{"student_id": p1.id, "status": "present"}, {"student_id": p1.id, "status": "absent"}]).status_code == 422
    assert mark(client, faculty, course["id"], d, [{"student_id": p1.id, "status": "sleeping"}]).status_code == 422
    assert mark(client, faculty, course["id"], d, []).status_code == 422


def test_students_only_see_their_own_attendance(client, faculty, stu1, stu2, course):
    for _, p in (stu1, stu2):
        enroll(client, faculty, course["id"], p)
    mark(client, faculty, course["id"], date.today() - timedelta(days=1),
         [{"student_id": stu1[1].id, "status": "present"}, {"student_id": stu2[1].id, "status": "absent"}])
    r1 = client.get("/api/v1/attendance/me/records", headers=auth(stu1[0])).json()
    assert [x["student_id"] for x in r1["items"]] == [stu1[1].id]
    # staff-only endpoints are closed to students, even for their own id
    assert client.get(f"/api/v1/attendance/students/{stu1[1].id}/summary", headers=auth(stu1[0])).status_code == 403
    assert client.get(f"/api/v1/attendance/courses/{course['id']}", headers=auth(stu1[0])).status_code == 403


def test_faculty_views_course_attendance_with_pagination_and_filter(client, faculty, stu1, stu2, course):
    for _, p in (stu1, stu2):
        enroll(client, faculty, course["id"], p)
    d1, d2 = date.today() - timedelta(days=2), date.today() - timedelta(days=1)
    for d in (d1, d2):
        mark(client, faculty, course["id"], d, [{"student_id": stu1[1].id, "status": "present"}, {"student_id": stu2[1].id, "status": "present"}])
    all_ = client.get(f"/api/v1/attendance/courses/{course['id']}?size=3", headers=auth(faculty)).json()
    assert all_["total"] == 4 and len(all_["items"]) == 3 and all_["pages"] == 2
    assert client.get(f"/api/v1/attendance/courses/{course['id']}?class_date={d1}", headers=auth(faculty)).json()["total"] == 2
    assert client.get(f"/api/v1/attendance/students/{stu1[1].id}/summary", headers=auth(faculty)).json()["overall_percentage"] == 100.0


def test_no_classes_yet_gives_null_percentage(client, faculty, stu1, course):
    enroll(client, faculty, course["id"], stu1[1])
    s = client.get("/api/v1/attendance/me/summary", headers=auth(stu1[0])).json()
    assert s["overall_percentage"] is None and s["courses"][0]["total_classes"] == 0
