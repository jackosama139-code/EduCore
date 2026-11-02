"""Authorization rules in ONE place. Routes call these; they never re-implement checks.
This is the heart of 'students can only see their own data'."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import Course, Enrollment, Role, StudentProfile, User


def get_student_profile_of(db: Session, user: User) -> StudentProfile:
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
    if not profile:
        raise NotFoundError("No student profile exists for this account yet; ask an admin to create it")
    return profile


def get_course_or_404(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise NotFoundError("Course not found")
    return course


def can_manage_course(course: Course, user: User) -> bool:
    return user.role == Role.admin or (user.role == Role.faculty and course.faculty_id == user.id)


def assert_can_manage_course(course: Course, user: User) -> None:
    if not can_manage_course(course, user):
        raise ForbiddenError("You do not manage this course")


def is_enrolled(db: Session, student_id: int, course_id: int) -> bool:
    return db.scalar(
        select(Enrollment.id).where(Enrollment.student_id == student_id, Enrollment.course_id == course_id)
    ) is not None


def assert_can_view_course(db: Session, course: Course, user: User) -> None:
    if can_manage_course(course, user):
        return
    if user.role == Role.student:
        profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
        if profile and is_enrolled(db, profile.id, course.id):
            return
    raise ForbiddenError("You do not have access to this course")


def faculty_teaches_student(db: Session, faculty_id: int, student_id: int) -> bool:
    return db.scalar(
        select(Enrollment.id)
        .join(Course, Course.id == Enrollment.course_id)
        .where(Enrollment.student_id == student_id, Course.faculty_id == faculty_id)
        .limit(1)
    ) is not None


def assert_can_view_student(db: Session, student: StudentProfile, user: User) -> None:
    if user.role == Role.admin:
        return
    if user.role == Role.student and student.user_id == user.id:
        return
    if user.role == Role.faculty and faculty_teaches_student(db, user.id, student.id):
        return
    # 404 (not 403) for students: don't even confirm that another student's record exists.
    if user.role == Role.student:
        raise NotFoundError("Student not found")
    raise ForbiddenError("You do not have access to this student")
