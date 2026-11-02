from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models import Course, Enrollment, Role, StudentProfile, User
from app.schemas.common import PageParams
from app.schemas.student import StudentCreate, StudentSelfUpdate, StudentUpdate
from app.services import access
from app.services.pagination import paginate


def create_profile(db: Session, data: StudentCreate) -> StudentProfile:
    user = db.get(User, data.user_id)
    if not user:
        raise NotFoundError("User not found")
    if user.role != Role.student:
        raise BadRequestError("Only users with the 'student' role can have a student profile")
    if db.scalar(select(StudentProfile.id).where(StudentProfile.user_id == user.id)):
        raise ConflictError("This user already has a student profile")
    profile = StudentProfile(**data.model_dump())
    db.add(profile)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Roll number already in use")
    return db.scalar(select(StudentProfile).options(joinedload(StudentProfile.user)).where(StudentProfile.id == profile.id))


def list_students(db: Session, user: User, params: PageParams, department: str | None, search: str | None):
    stmt = select(StudentProfile).join(User, User.id == StudentProfile.user_id).options(joinedload(StudentProfile.user))
    if user.role == Role.faculty:  # faculty see only students enrolled in THEIR courses
        stmt = stmt.where(
            StudentProfile.id.in_(
                select(Enrollment.student_id).join(Course, Course.id == Enrollment.course_id).where(Course.faculty_id == user.id)
            )
        )
    if department:
        stmt = stmt.where(StudentProfile.department == department)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(User.full_name.ilike(like), StudentProfile.roll_number.ilike(like)))
    return paginate(db, stmt.order_by(StudentProfile.roll_number), params)


def get_student(db: Session, student_id: int, user: User) -> StudentProfile:
    student = db.scalar(
        select(StudentProfile).options(joinedload(StudentProfile.user)).where(StudentProfile.id == student_id)
    )
    if not student:
        raise NotFoundError("Student not found")
    access.assert_can_view_student(db, student, user)
    return student


def get_own(db: Session, user: User) -> StudentProfile:
    profile = access.get_student_profile_of(db, user)
    return get_student(db, profile.id, user)


def _apply_update(db: Session, student: StudentProfile, changes: dict) -> StudentProfile:
    for k, v in changes.items():
        setattr(student, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Roll number already in use")
    return student


def update_student(db: Session, student_id: int, data: StudentUpdate) -> StudentProfile:
    student = db.get(StudentProfile, student_id)
    if not student:
        raise NotFoundError("Student not found")
    return _apply_update(db, student, data.model_dump(exclude_unset=True))


def update_own(db: Session, user: User, data: StudentSelfUpdate) -> StudentProfile:
    student = access.get_student_profile_of(db, user)
    return _apply_update(db, student, data.model_dump(exclude_unset=True))
