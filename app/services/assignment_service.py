from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models import Assignment, Course, Enrollment, Submission, User
from app.schemas.assignment import AssignmentCreate, GradeIn, SubmissionCreate
from app.schemas.common import PageParams
from app.services import access
from app.services.pagination import paginate


def as_utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; PostgreSQL returns aware ones. Normalise before comparing."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def get_assignment_or_404(db: Session, assignment_id: int) -> Assignment:
    a = db.get(Assignment, assignment_id)
    if not a:
        raise NotFoundError("Assignment not found")
    return a


def create_assignment(db: Session, course_id: int, user: User, data: AssignmentCreate) -> Assignment:
    course = access.get_course_or_404(db, course_id)
    access.assert_can_manage_course(course, user)
    a = Assignment(course_id=course_id, created_by=user.id, **data.model_dump())
    db.add(a)
    db.commit()
    return a


def list_assignments(db: Session, course_id: int, user: User, params: PageParams):
    course = access.get_course_or_404(db, course_id)
    access.assert_can_view_course(db, course, user)
    stmt = select(Assignment).where(Assignment.course_id == course_id).order_by(Assignment.due_date)
    return paginate(db, stmt, params)


def get_assignment(db: Session, assignment_id: int, user: User) -> Assignment:
    a = get_assignment_or_404(db, assignment_id)
    access.assert_can_view_course(db, access.get_course_or_404(db, a.course_id), user)
    return a


def delete_assignment(db: Session, assignment_id: int, user: User) -> None:
    a = get_assignment_or_404(db, assignment_id)
    access.assert_can_manage_course(access.get_course_or_404(db, a.course_id), user)
    db.delete(a)
    db.commit()


def submit(db: Session, assignment_id: int, user: User, data: SubmissionCreate) -> Submission:
    a = get_assignment_or_404(db, assignment_id)
    student = access.get_student_profile_of(db, user)
    if not access.is_enrolled(db, student.id, a.course_id):
        raise ForbiddenError("You are not enrolled in this course")
    if db.scalar(select(Submission.id).where(Submission.assignment_id == a.id, Submission.student_id == student.id)):
        raise ConflictError("You have already submitted this assignment")
    now = datetime.now(timezone.utc)
    sub = Submission(assignment_id=a.id, student_id=student.id, content=data.content, submitted_at=now,
                     is_late=now > as_utc(a.due_date))
    db.add(sub)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("You have already submitted this assignment")
    return sub


def list_submissions(db: Session, assignment_id: int, user: User, params: PageParams):
    a = get_assignment_or_404(db, assignment_id)
    access.assert_can_manage_course(access.get_course_or_404(db, a.course_id), user)
    stmt = select(Submission).where(Submission.assignment_id == assignment_id).order_by(Submission.submitted_at)
    return paginate(db, stmt, params)


def list_my_submissions(db: Session, user: User, params: PageParams):
    student = access.get_student_profile_of(db, user)
    stmt = select(Submission).where(Submission.student_id == student.id).order_by(Submission.submitted_at.desc())
    return paginate(db, stmt, params)


def grade(db: Session, submission_id: int, user: User, data: GradeIn) -> Submission:
    sub = db.get(Submission, submission_id)
    if not sub:
        raise NotFoundError("Submission not found")
    a = db.get(Assignment, sub.assignment_id)
    access.assert_can_manage_course(access.get_course_or_404(db, a.course_id), user)
    if data.marks > a.max_marks:
        raise BadRequestError(f"Marks cannot exceed the maximum of {a.max_marks}")
    sub.marks, sub.feedback, sub.graded_by = data.marks, data.feedback, user.id
    db.commit()
    return sub
