from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Role, User
from app.schemas.common import Page, PageParams, make_page
from app.schemas.course import CourseOut
from app.schemas.student import StudentCreate, StudentOut, StudentSelfUpdate, StudentUpdate
from app.services import course_service, student_service

router = APIRouter(prefix="/students", tags=["Students"])
admin_only = require_roles(Role.admin)
staff = require_roles(Role.admin, Role.faculty)
student_only = require_roles(Role.student)


@router.post("", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(data: StudentCreate, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return student_service.create_profile(db, data)


@router.get("", response_model=Page[StudentOut])
def list_students(
    department: str | None = None,
    search: str | None = Query(None, max_length=100, description="Name or roll number"),
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(staff),
):
    items, total = student_service.list_students(db, user, params, department, search)
    return make_page(items, total, params)


# NOTE: /me routes are declared BEFORE /{student_id}, otherwise "me" would be parsed as an id.
@router.get("/me", response_model=StudentOut)
def my_profile(db: Session = Depends(get_db), user: User = Depends(student_only)):
    return student_service.get_own(db, user)


@router.put("/me", response_model=StudentOut)
def update_my_profile(data: StudentSelfUpdate, db: Session = Depends(get_db), user: User = Depends(student_only)):
    return student_service.update_own(db, user, data)


@router.get("/me/courses", response_model=Page[CourseOut])
def my_courses(params: PageParams = Depends(), db: Session = Depends(get_db), user: User = Depends(student_only)):
    items, total = course_service.list_courses(db, user, params, active_only=None)
    return make_page(items, total, params)


@router.get("/{student_id}", response_model=StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return student_service.get_student(db, student_id, user)


@router.put("/{student_id}", response_model=StudentOut)
def update_student(student_id: int, data: StudentUpdate, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return student_service.update_student(db, student_id, data)
