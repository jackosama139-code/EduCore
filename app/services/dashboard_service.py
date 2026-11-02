from datetime import datetime, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Assignment, AttendanceRecord, Course, Enrollment, Role, Submission, User
from app.schemas.dashboard import (AdminDashboard, AssignmentStats, AttendanceStats, FacultyDashboard,
                                   StudentAssignmentStats, StudentDashboard)
from app.services import access, attendance_service
from app.services.assignment_service import as_utc
from app.services.attendance_service import ATTENDED, percentage


def _count(db: Session, stmt) -> int:
    return db.scalar(stmt) or 0


def _attendance_stats(db: Session, course_ids=None) -> AttendanceStats:
    stmt = select(func.count(AttendanceRecord.id),
                  func.coalesce(func.sum(case((AttendanceRecord.status.in_(ATTENDED), 1), else_=0)), 0))
    if course_ids is not None:
        stmt = stmt.where(AttendanceRecord.course_id.in_(course_ids))
    total, attended = db.execute(stmt).one()
    return AttendanceStats(total_records=total, attended_records=int(attended), overall_percentage=percentage(int(attended), total))


def _assignment_stats(db: Session, course_ids=None) -> AssignmentStats:
    a_stmt = select(func.count(Assignment.id))
    s_stmt = select(
        func.count(Submission.id),
        func.coalesce(func.sum(case((Submission.marks.is_not(None), 1), else_=0)), 0),
        func.coalesce(func.sum(case((Submission.is_late.is_(True), 1), else_=0)), 0),
        func.avg(case((Submission.marks.is_not(None), Submission.marks * 100.0 / Assignment.max_marks))),
    ).join(Assignment, Assignment.id == Submission.assignment_id)
    if course_ids is not None:
        a_stmt = a_stmt.where(Assignment.course_id.in_(course_ids))
        s_stmt = s_stmt.where(Assignment.course_id.in_(course_ids))
    subs, graded, late, avg = db.execute(s_stmt).one()
    return AssignmentStats(
        total_assignments=_count(db, a_stmt), total_submissions=subs, graded_submissions=int(graded),
        pending_grading=subs - int(graded), late_submissions=int(late),
        average_score_percent=round(float(avg), 2) if avg is not None else None,
    )


def admin_dashboard(db: Session) -> AdminDashboard:
    return AdminDashboard(
        student_count=_count(db, select(func.count(User.id)).where(User.role == Role.student)),
        faculty_count=_count(db, select(func.count(User.id)).where(User.role == Role.faculty)),
        course_count=_count(db, select(func.count(Course.id))),
        active_course_count=_count(db, select(func.count(Course.id)).where(Course.is_active.is_(True))),
        enrollment_count=_count(db, select(func.count(Enrollment.id))),
        attendance=_attendance_stats(db),
        assignments=_assignment_stats(db),
    )


def faculty_dashboard(db: Session, user: User) -> FacultyDashboard:
    course_ids = select(Course.id).where(Course.faculty_id == user.id)
    return FacultyDashboard(
        course_count=_count(db, select(func.count(Course.id)).where(Course.faculty_id == user.id)),
        student_count=_count(db, select(func.count(func.distinct(Enrollment.student_id))).where(Enrollment.course_id.in_(course_ids))),
        attendance=_attendance_stats(db, course_ids),
        assignments=_assignment_stats(db, course_ids),
    )


def student_dashboard(db: Session, user: User) -> StudentDashboard:
    student = access.get_student_profile_of(db, user)
    summary = attendance_service.student_summary(db, student.id)
    now = datetime.now(timezone.utc)

    enrolled = select(Enrollment.course_id).where(Enrollment.student_id == student.id)
    assignments = db.execute(select(Assignment.id, Assignment.due_date).where(Assignment.course_id.in_(enrolled))).all()
    subs = {
        s.assignment_id: s
        for s in db.scalars(select(Submission).where(Submission.student_id == student.id))
    }
    pending = overdue = 0
    for aid, due in assignments:
        if aid not in subs:
            if as_utc(due) < now:
                overdue += 1
            else:
                pending += 1
    avg = db.scalar(
        select(func.avg(Submission.marks * 100.0 / Assignment.max_marks))
        .select_from(Submission)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .where(Submission.student_id == student.id, Submission.marks.is_not(None))
    )
    return StudentDashboard(
        enrolled_courses=len(summary.courses),
        attendance_percentage=summary.overall_percentage,
        courses_below_threshold=sum(c.below_threshold for c in summary.courses),
        assignments=StudentAssignmentStats(
            total=len(assignments), submitted=len(subs), pending=pending, overdue=overdue,
            graded=sum(1 for s in subs.values() if s.marks is not None),
            average_score_percent=round(float(avg), 2) if avg is not None else None,
        ),
    )
