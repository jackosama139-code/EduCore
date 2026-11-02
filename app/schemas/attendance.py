from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AttendanceStatus


class AttendanceItem(BaseModel):
    student_id: int
    status: AttendanceStatus


class AttendanceMark(BaseModel):
    class_date: date
    records: list[AttendanceItem] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def no_duplicate_students(self):
        ids = [r.student_id for r in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate student_id in records")
        return self


class AttendanceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    course_id: int
    student_id: int
    class_date: date
    status: AttendanceStatus


class CourseAttendanceSummary(BaseModel):
    course_id: int
    course_code: str
    course_title: str
    total_classes: int
    attended: int  # present + late
    percentage: float | None  # None when no classes held yet
    below_threshold: bool


class AttendanceSummary(BaseModel):
    student_id: int
    overall_percentage: float | None
    threshold: float
    courses: list[CourseAttendanceSummary]
