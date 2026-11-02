from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Role, User
from app.schemas.common import Page, PageParams, make_page
from app.schemas.course import CourseCreate, CourseOut, CourseUpdate, EnrollmentCreate, EnrollmentOut
from app.schemas.student import StudentOut
from app.services import course_service

router = APIRouter(prefix="/courses", tags=["Courses"])
staff = require_roles(Role.admin, Role.faculty)


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(data: CourseCreate, db: Session = Depends(get_db), user: User = Depends(staff)):
    return course_service.create_course(db, user, data)


@router.get("", response_model=Page[CourseOut])
def list_courses(
    active: bool | None = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Role-aware: admin = all, faculty = own, student = enrolled."""
    items, total = course_service.list_courses(db, user, params, active)
    return make_page(items, total, params)


@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return course_service.get_course_for_user(db, course_id, user)


@router.put("/{course_id}", response_model=CourseOut)
def update_course(course_id: int, data: CourseUpdate, db: Session = Depends(get_db), user: User = Depends(staff)):
    return course_service.update_course(db, course_id, user, data)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    course_service.delete_course(db, course_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{course_id}/enrollments", response_model=EnrollmentOut, status_code=status.HTTP_201_CREATED)
def enroll_student(course_id: int, data: EnrollmentCreate, db: Session = Depends(get_db), user: User = Depends(staff)):
    return course_service.enroll(db, course_id, data.student_id, user)


@router.delete("/{course_id}/enrollments/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def unenroll_student(course_id: int, student_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    course_service.unenroll(db, course_id, student_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{course_id}/students", response_model=Page[StudentOut])
def course_students(course_id: int, params: PageParams = Depends(), db: Session = Depends(get_db), user: User = Depends(staff)):
    items, total = course_service.list_course_students(db, course_id, user, params)
    return make_page(items, total, params)
