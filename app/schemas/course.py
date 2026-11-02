from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CourseCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    credits: int = Field(3, ge=1, le=10)
    faculty_id: int | None = None  # only honoured for admins


class CourseUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    credits: int | None = Field(None, ge=1, le=10)
    is_active: bool | None = None
    faculty_id: int | None = None  # only honoured for admins


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    title: str
    description: str | None
    credits: int
    faculty_id: int
    faculty_name: str
    is_active: bool
    created_at: datetime


class EnrollmentCreate(BaseModel):
    student_id: int


class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: int
    course_id: int
    enrolled_at: datetime
