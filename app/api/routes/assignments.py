from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Role, User
from app.schemas.assignment import AssignmentCreate, AssignmentOut, GradeIn, SubmissionCreate, SubmissionOut
from app.schemas.common import Page, PageParams, make_page
from app.services import assignment_service

router = APIRouter(tags=["Assignments"])
staff = require_roles(Role.admin, Role.faculty)
student_only = require_roles(Role.student)


@router.post("/courses/{course_id}/assignments", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
def create_assignment(course_id: int, data: AssignmentCreate, db: Session = Depends(get_db), user: User = Depends(staff)):
    return assignment_service.create_assignment(db, course_id, user, data)


@router.get("/courses/{course_id}/assignments", response_model=Page[AssignmentOut])
def list_assignments(course_id: int, params: PageParams = Depends(), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items, total = assignment_service.list_assignments(db, course_id, user, params)
    return make_page(items, total, params)


@router.get("/assignments/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return assignment_service.get_assignment(db, assignment_id, user)


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    assignment_service.delete_assignment(db, assignment_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/assignments/{assignment_id}/submissions", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
def submit_assignment(assignment_id: int, data: SubmissionCreate, db: Session = Depends(get_db), user: User = Depends(student_only)):
    return assignment_service.submit(db, assignment_id, user, data)


@router.get("/assignments/{assignment_id}/submissions", response_model=Page[SubmissionOut])
def list_submissions(assignment_id: int, params: PageParams = Depends(), db: Session = Depends(get_db), user: User = Depends(staff)):
    items, total = assignment_service.list_submissions(db, assignment_id, user, params)
    return make_page(items, total, params)


@router.get("/submissions/me", response_model=Page[SubmissionOut])
def my_submissions(params: PageParams = Depends(), db: Session = Depends(get_db), user: User = Depends(student_only)):
    items, total = assignment_service.list_my_submissions(db, user, params)
    return make_page(items, total, params)


@router.put("/submissions/{submission_id}/grade", response_model=SubmissionOut)
def grade_submission(submission_id: int, data: GradeIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    return assignment_service.grade(db, submission_id, user, data)
