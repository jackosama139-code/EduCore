from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import Role, User
from app.schemas.dashboard import AdminDashboard, FacultyDashboard, StudentDashboard
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/admin", response_model=AdminDashboard)
def admin_dashboard(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.admin))):
    return dashboard_service.admin_dashboard(db)


@router.get("/faculty", response_model=FacultyDashboard)
def faculty_dashboard(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.faculty))):
    return dashboard_service.faculty_dashboard(db, user)


@router.get("/student", response_model=StudentDashboard)
def student_dashboard(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.student))):
    return dashboard_service.student_dashboard(db, user)
