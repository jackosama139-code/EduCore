import enum


class Role(str, enum.Enum):
    admin = "admin"
    faculty = "faculty"
    student = "student"


class AttendanceStatus(str, enum.Enum):
    present = "present"
    absent = "absent"
    late = "late"  # counts as attended
