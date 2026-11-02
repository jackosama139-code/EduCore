from pydantic import BaseModel


class AttendanceStats(BaseModel):
    total_records: int
    attended_records: int
    overall_percentage: float | None


class AssignmentStats(BaseModel):
    total_assignments: int
    total_submissions: int
    graded_submissions: int
    pending_grading: int
    late_submissions: int
    average_score_percent: float | None


class AdminDashboard(BaseModel):
    student_count: int
    faculty_count: int
    course_count: int
    active_course_count: int
    enrollment_count: int
    attendance: AttendanceStats
    assignments: AssignmentStats


class FacultyDashboard(BaseModel):
    course_count: int
    student_count: int
    attendance: AttendanceStats
    assignments: AssignmentStats


class StudentAssignmentStats(BaseModel):
    total: int
    submitted: int
    pending: int  # not submitted, deadline still ahead
    overdue: int  # not submitted, deadline passed
    graded: int
    average_score_percent: float | None


class StudentDashboard(BaseModel):
    enrolled_courses: int
    attendance_percentage: float | None
    courses_below_threshold: int
    assignments: StudentAssignmentStats
