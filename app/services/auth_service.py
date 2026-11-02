from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.models import Role, User
from app.schemas.user import UserCreate


def create_user(db: Session, data: UserCreate, role: Role) -> User:
    email = data.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("Email already registered")
    user = User(email=email, full_name=data.full_name.strip(), hashed_password=hash_password(data.password), role=role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two requests racing past the check above
        db.rollback()
        raise ConflictError("Email already registered")
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    # Same message for "no such user" and "wrong password" -> no account enumeration.
    if not user or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Incorrect email or password")
    if not user.is_active:
        raise ForbiddenError("Account is disabled")
    return user
