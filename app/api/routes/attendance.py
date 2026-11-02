from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import Role, User
from app.schemas.attendance import AttendanceMark, AttendanceRecordOut, AttendanceSummary
from app.schemas.common import Page, PageParams, make_page
from app.services import access, attendance_service

router = APIRouter(prefix="/attendance", tags=["Attendance"])
staff = require_roles(Role.admin, Role.faculty)
student_only = require_roles(Role.student)


@router.post("/courses/{course_id}", response_model=list[AttendanceRecordOut])
def mark_attendance(course_id: int, data: AttendanceMark, db: Session = Depends(get_db), user: User = Depends(staff)):
    """Record (or correct) attendance for one class day. Idempotent per student/day."""
    return attendance_service.mark_attendance(db, course_id, user, data)


@router.get("/courses/{course_id}", response_model=Page[AttendanceRecordOut])
def course_attendance(
    course_id: int,
    class_date: date | None = Query(None),
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(staff),
):
    items, total = attendance_service.list_course_attendance(db, course_id, user, params, class_date)
    return make_page(items, total, params)


# ---- the logged-in student's OWN data: the student id is never taken from the URL ----
@router.get("/me/summary", response_model=AttendanceSummary)
def my_summary(db: Session = Depends(get_db), user: User = Depends(student_only)):
    return attendance_service.student_summary(db, access.get_student_profile_of(db, user).id)


@router.get("/me/records", response_model=Page[AttendanceRecordOut])
def my_records(
    course_id: int | None = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(student_only),
):
    sid = access.get_student_profile_of(db, user).id
    items, total = attendance_service.list_student_records(db, sid, params, course_id)
    return make_page(items, total, params)


# ---- staff looking at one student ----
@router.get("/students/{student_id}/summary", response_model=AttendanceSummary)
def student_summary(student_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    return attendance_service.summary_for_user(db, student_id, user)
