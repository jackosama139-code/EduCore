from datetime import date

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models import AttendanceRecord, AttendanceStatus, Course, Enrollment, Role, StudentProfile, User
from app.schemas.attendance import AttendanceMark, AttendanceSummary, CourseAttendanceSummary
from app.schemas.common import PageParams
from app.services import access
from app.services.pagination import paginate

ATTENDED = (AttendanceStatus.present, AttendanceStatus.late)


def percentage(attended: int, total: int) -> float | None:
    """Attendance % = (present + late) / total classes * 100, 2 decimals. None if no classes yet."""
    return round(attended / total * 100, 2) if total else None


def mark_attendance(db: Session, course_id: int, user: User, data: AttendanceMark) -> list[AttendanceRecord]:
    course = access.get_course_or_404(db, course_id)
    access.assert_can_manage_course(course, user)
    if data.class_date > date.today():
        raise BadRequestError("Cannot record attendance for a future date")

    ids = [r.student_id for r in data.records]
    enrolled = set(db.scalars(select(Enrollment.student_id).where(Enrollment.course_id == course_id, Enrollment.student_id.in_(ids))))
    missing = sorted(set(ids) - enrolled)
    if missing:
        raise BadRequestError(f"Students not enrolled in this course: {missing}")

    # Upsert: re-submitting the same day corrects earlier mistakes instead of failing.
    existing = {
        r.student_id: r
        for r in db.scalars(
            select(AttendanceRecord).where(
                AttendanceRecord.course_id == course_id,
                AttendanceRecord.class_date == data.class_date,
                AttendanceRecord.student_id.in_(ids),
            )
        )
    }
    result = []
    for item in data.records:
        rec = existing.get(item.student_id)
        if rec:
            rec.status, rec.marked_by = item.status, user.id
        else:
            rec = AttendanceRecord(
                course_id=course_id, student_id=item.student_id, class_date=data.class_date,
                status=item.status, marked_by=user.id,
            )
            db.add(rec)
        result.append(rec)
    db.commit()
    return result


def list_course_attendance(db: Session, course_id: int, user: User, params: PageParams, class_date: date | None):
    course = access.get_course_or_404(db, course_id)
    access.assert_can_manage_course(course, user)
    stmt = select(AttendanceRecord).where(AttendanceRecord.course_id == course_id)
    if class_date:
        stmt = stmt.where(AttendanceRecord.class_date == class_date)
    return paginate(db, stmt.order_by(AttendanceRecord.class_date.desc(), AttendanceRecord.student_id), params)


def list_student_records(db: Session, student_id: int, params: PageParams, course_id: int | None, faculty_id: int | None = None):
    stmt = select(AttendanceRecord).where(AttendanceRecord.student_id == student_id)
    if course_id:
        stmt = stmt.where(AttendanceRecord.course_id == course_id)
    if faculty_id:  # faculty only see attendance in courses they teach
        stmt = stmt.where(AttendanceRecord.course_id.in_(select(Course.id).where(Course.faculty_id == faculty_id)))
    return paginate(db, stmt.order_by(AttendanceRecord.class_date.desc()), params)


def student_summary(db: Session, student_id: int, faculty_id: int | None = None) -> AttendanceSummary:
    attended_expr = func.coalesce(func.sum(case((AttendanceRecord.status.in_(ATTENDED), 1), else_=0)), 0)
    stmt = (
        select(Course.id, Course.code, Course.title, func.count(AttendanceRecord.id), attended_expr)
        .select_from(Enrollment)
        .join(Course, Course.id == Enrollment.course_id)
        .outerjoin(
            AttendanceRecord,
            and_(AttendanceRecord.course_id == Course.id, AttendanceRecord.student_id == Enrollment.student_id),
        )
        .where(Enrollment.student_id == student_id)
        .group_by(Course.id, Course.code, Course.title)
        .order_by(Course.code)
    )
    if faculty_id:
        stmt = stmt.where(Course.faculty_id == faculty_id)

    courses, tot_all, att_all = [], 0, 0
    for cid, code, title, total, attended in db.execute(stmt):
        pct = percentage(int(attended), total)
        courses.append(CourseAttendanceSummary(
            course_id=cid, course_code=code, course_title=title, total_classes=total, attended=int(attended),
            percentage=pct, below_threshold=pct is not None and pct < settings.ATTENDANCE_THRESHOLD,
        ))
        tot_all += total
        att_all += int(attended)
    return AttendanceSummary(
        student_id=student_id, overall_percentage=percentage(att_all, tot_all),
        threshold=settings.ATTENDANCE_THRESHOLD, courses=courses,
    )


def summary_for_user(db: Session, student_id: int, user: User) -> AttendanceSummary:
    """Admin/faculty/student viewing a student's summary, with the proper visibility filter."""
    student = db.get(StudentProfile, student_id)
    if not student:
        raise NotFoundError("Student not found")
    access.assert_can_view_student(db, student, user)
    return student_summary(db, student_id, faculty_id=user.id if user.role == Role.faculty else None)
