from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models import Course, Enrollment, Role, StudentProfile, User
from app.schemas.common import PageParams
from app.schemas.course import CourseCreate, CourseUpdate
from app.services import access
from app.services.pagination import paginate


def _faculty_or_error(db: Session, faculty_id: int) -> User:
    f = db.get(User, faculty_id)
    if not f or f.role != Role.faculty:
        raise BadRequestError("faculty_id must refer to a user with the 'faculty' role")
    return f


def create_course(db: Session, user: User, data: CourseCreate) -> Course:
    if user.role == Role.admin:
        if data.faculty_id is None:
            raise BadRequestError("Admins must supply faculty_id when creating a course")
        faculty_id = _faculty_or_error(db, data.faculty_id).id
    else:
        faculty_id = user.id  # faculty always create courses for themselves
    code = data.code.strip().upper()
    if db.scalar(select(Course.id).where(Course.code == code)):
        raise ConflictError("Course code already exists")
    course = Course(code=code, title=data.title, description=data.description, credits=data.credits, faculty_id=faculty_id)
    db.add(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Course code already exists")
    return get_course(db, course.id)


def get_course(db: Session, course_id: int) -> Course:
    course = db.scalar(select(Course).options(joinedload(Course.faculty)).where(Course.id == course_id))
    if not course:
        raise NotFoundError("Course not found")
    return course


def get_course_for_user(db: Session, course_id: int, user: User) -> Course:
    course = get_course(db, course_id)
    access.assert_can_view_course(db, course, user)
    return course


def list_courses(db: Session, user: User, params: PageParams, active_only: bool | None):
    stmt = select(Course).options(joinedload(Course.faculty))
    if user.role == Role.faculty:
        stmt = stmt.where(Course.faculty_id == user.id)
    elif user.role == Role.student:
        profile = access.get_student_profile_of(db, user)
        stmt = stmt.join(Enrollment, Enrollment.course_id == Course.id).where(Enrollment.student_id == profile.id)
    if active_only is not None:
        stmt = stmt.where(Course.is_active == active_only)
    return paginate(db, stmt.order_by(Course.code), params)


def update_course(db: Session, course_id: int, user: User, data: CourseUpdate) -> Course:
    course = get_course(db, course_id)
    access.assert_can_manage_course(course, user)
    changes = data.model_dump(exclude_unset=True)
    new_faculty = changes.pop("faculty_id", None)
    if new_faculty is not None:
        if user.role != Role.admin:
            raise ForbiddenError("Only admins can reassign a course")
        course.faculty_id = _faculty_or_error(db, new_faculty).id
    for k, v in changes.items():
        setattr(course, k, v)
    db.commit()
    return get_course(db, course_id)


def delete_course(db: Session, course_id: int, user: User) -> None:
    course = get_course(db, course_id)
    access.assert_can_manage_course(course, user)
    db.delete(course)  # cascades to enrollments, assignments, submissions
    db.commit()


# ---- enrollment ----------------------------------------------------------
def enroll(db: Session, course_id: int, student_id: int, user: User) -> Enrollment:
    course = get_course(db, course_id)
    access.assert_can_manage_course(course, user)
    if not course.is_active:
        raise BadRequestError("Cannot enroll students in an inactive course")
    if not db.get(StudentProfile, student_id):
        raise NotFoundError("Student not found")
    if access.is_enrolled(db, student_id, course_id):
        raise ConflictError("Student is already enrolled in this course")
    enrollment = Enrollment(course_id=course_id, student_id=student_id)
    db.add(enrollment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Student is already enrolled in this course")
    return enrollment


def unenroll(db: Session, course_id: int, student_id: int, user: User) -> None:
    course = get_course(db, course_id)
    access.assert_can_manage_course(course, user)
    enrollment = db.scalar(select(Enrollment).where(Enrollment.course_id == course_id, Enrollment.student_id == student_id))
    if not enrollment:
        raise NotFoundError("Enrollment not found")
    db.delete(enrollment)
    db.commit()


def list_course_students(db: Session, course_id: int, user: User, params: PageParams):
    course = get_course(db, course_id)
    access.assert_can_manage_course(course, user)
    stmt = (
        select(StudentProfile)
        .join(Enrollment, Enrollment.student_id == StudentProfile.id)
        .options(joinedload(StudentProfile.user))
        .where(Enrollment.course_id == course_id)
        .order_by(StudentProfile.roll_number)
    )
    return paginate(db, stmt, params)
