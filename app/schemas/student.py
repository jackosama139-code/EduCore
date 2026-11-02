from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class StudentCreate(BaseModel):
    user_id: int
    roll_number: str = Field(min_length=1, max_length=30)
    department: str = Field(min_length=1, max_length=100)
    semester: int = Field(1, ge=1, le=8)
    admission_year: int | None = Field(None, ge=2000, le=2100)
    phone: str | None = Field(None, max_length=20)
    date_of_birth: date | None = None


class StudentUpdate(BaseModel):
    """Admin can change everything except the owning user."""
    roll_number: str | None = Field(None, min_length=1, max_length=30)
    department: str | None = Field(None, min_length=1, max_length=100)
    semester: int | None = Field(None, ge=1, le=8)
    admission_year: int | None = Field(None, ge=2000, le=2100)
    phone: str | None = Field(None, max_length=20)
    date_of_birth: date | None = None


class StudentSelfUpdate(BaseModel):
    """A student may only edit contact details - never roll number, department, semester."""
    phone: str | None = Field(None, max_length=20)
    date_of_birth: date | None = None


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    full_name: str
    email: str
    roll_number: str
    department: str
    semester: int
    admission_year: int | None
    phone: str | None
    date_of_birth: date | None
