from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.schemas.common import PageParams


def paginate(db: Session, stmt: Select, params: PageParams):
    """Run COUNT(*) over the filtered query, then fetch just one page."""
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(stmt.limit(params.size).offset(params.offset)).unique().all()
    return items, total
