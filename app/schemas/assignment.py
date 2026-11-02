from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssignmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    due_date: datetime
    max_marks: float = Field(100, gt=0, le=1000)

    @field_validator("due_date")
    @classmethod
    def to_utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    course_id: int
    title: str
    description: str | None
    due_date: datetime
    max_marks: float
    created_at: datetime


class SubmissionCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


class GradeIn(BaseModel):
    marks: float = Field(ge=0)
    feedback: str | None = Field(None, max_length=2000)


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    assignment_id: int
    student_id: int
    content: str
    submitted_at: datetime
    is_late: bool
    marks: float | None
    feedback: str | None
