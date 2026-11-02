from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def enum_col(enum_cls, length: int = 20) -> SAEnum:
    """Store enums as VARCHAR + CHECK constraint (portable, easy to migrate)
    instead of native PostgreSQL ENUM types, which are painful to alter."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )
