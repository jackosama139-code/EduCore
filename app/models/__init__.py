# Import every model so Base.metadata (and Alembic autogenerate) sees all tables.
from app.models.assignment import Assignment, Submission  # noqa: F401
from app.models.academic import Course, Enrollment, StudentProfile  # noqa: F401
from app.models.attendance import AttendanceRecord  # noqa: F401
from app.models.document import Document, DocumentChunk  # noqa: F401
from app.models.enums import AttendanceStatus, Role  # noqa: F401
from app.models.user import User  # noqa: F401
