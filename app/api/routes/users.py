from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.exceptions import BadRequestError, NotFoundError
from app.db.session import get_db
from app.models import Role, User
from app.schemas.common import Page, PageParams, make_page
from app.schemas.user import AdminUserCreate, UserOut, UserStatusUpdate
from app.services import auth_service
from app.services.pagination import paginate

router = APIRouter(prefix="/users", tags=["Users (admin)"])
admin_only = require_roles(Role.admin)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: AdminUserCreate, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    """Admin creates accounts of any role (this is how faculty/admin accounts are made)."""
    return auth_service.create_user(db, data, data.role)


@router.get("", response_model=Page[UserOut])
def list_users(
    role: Role | None = Query(None),
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
):
    stmt = select(User).order_by(User.id)
    if role:
        stmt = stmt.where(User.role == role)
    items, total = paginate(db, stmt, params)
    return make_page(items, total, params)


@router.patch("/{user_id}/status", response_model=UserOut)
def set_user_status(user_id: int, data: UserStatusUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    if user.id == admin.id and not data.is_active:
        raise BadRequestError("You cannot deactivate your own account")
    user.is_active = data.is_active
    db.commit()
    return user
