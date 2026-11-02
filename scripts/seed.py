"""Seed a realistic demo college. Idempotent: safe to run twice.

    python -m scripts.seed

Requires SEED_DEFAULT_PASSWORD in the environment/.env (never hardcoded).
"""
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (Assignment, AttendanceRecord, AttendanceStatus, Course, Enrollment, Role,
                        StudentProfile, Submission, User)

random.seed(42)  # deterministic demo data

FACULTY = [
    ("Dr. Anita Deshmukh", "anita.deshmukh"), ("Prof. Rahul Kulkarni", "rahul.kulkarni"),
    ("Dr. Meera Iyer", "meera.iyer"), ("Prof. Sanjay Patil", "sanjay.patil"),
]
COURSES = [  # code, title, credits, faculty index
    ("CS201", "Data Structures & Algorithms", 4, 0), ("CS202", "Database Management Systems", 4, 1),
    ("CS203", "Operating Systems", 3, 2), ("CS204", "Computer Networks", 3, 3),
    ("CS205", "Python Backend Development", 3, 1), ("MA201", "Discrete Mathematics", 3, 0),
]
FIRST = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Arjun", "Sai", "Reyansh", "Krish", "Ananya", "Diya", "Isha",
         "Saanvi", "Priya", "Riya", "Neha", "Kavya", "Rohan", "Karan", "Tanvi", "Sneha"]
LAST = ["Sharma", "Patil", "Joshi", "Kulkarni", "Mehta", "Nair", "Reddy", "Gupta", "Desai", "Shah"]
ASSIGNMENTS = ["Assignment 1 - Fundamentals", "Assignment 2 - Problem Set", "Lab Report"]


def get_or_create_user(db, email, name, role, password):
    u = db.scalar(select(User).where(User.email == email))
    if not u:
        u = User(email=email, full_name=name, role=role, hashed_password=password)
        db.add(u)
        db.flush()
    return u


def main() -> None:
    plain = os.environ.get("SEED_DEFAULT_PASSWORD")
    if not plain:
        sys.exit("Set SEED_DEFAULT_PASSWORD in your environment or .env first.")
    pw = hash_password(plain)  # hash once; bcrypt is deliberately slow
    db = SessionLocal()
    try:
        if db.scalar(select(User.id).where(User.email == "admin@educore.edu")):
            print("Seed data already present - nothing to do.")
            return
        get_or_create_user(db, "admin@educore.edu", "College Administrator", Role.admin, pw)
        faculty = [get_or_create_user(db, f"{h}@educore.edu", n, Role.faculty, pw) for n, h in FACULTY]

        courses = []
        for code, title, credits, fi in COURSES:
            c = Course(code=code, title=title, credits=credits, faculty_id=faculty[fi].id,
                       description=f"{title} - semester 4, Computer Engineering")
            db.add(c)
            courses.append(c)
        db.flush()

        students = []
        for i in range(30):
            name = f"{FIRST[i % len(FIRST)]} {LAST[(i * 3) % len(LAST)]}"
            u = get_or_create_user(db, f"student{i + 1:02d}@educore.edu", name, Role.student, pw)
            p = StudentProfile(user_id=u.id, roll_number=f"CE24{i + 1:03d}", department="Computer Engineering",
                               semester=4, admission_year=2023, phone=f"98765{i:05d}")
            db.add(p)
            students.append(p)
        db.flush()

        # each student takes 4 of the 6 courses
        enrolled: dict[int, list[StudentProfile]] = {c.id: [] for c in courses}
        for s in students:
            for c in random.sample(courses, 4):
                db.add(Enrollment(student_id=s.id, course_id=c.id))
                enrolled[c.id].append(s)

        # ~16 class days of attendance; every student has their own "attendance habit"
        habit = {s.id: random.choice([0.95, 0.9, 0.85, 0.8, 0.7, 0.6]) for s in students}
        days, d = [], date.today() - timedelta(days=1)
        while len(days) < 16:
            if d.weekday() < 5:
                days.append(d)
            d -= timedelta(days=1)
        for c in courses:
            for day in days:
                for s in enrolled[c.id]:
                    r = random.random()
                    st = (AttendanceStatus.present if r < habit[s.id] else
                          AttendanceStatus.late if r < habit[s.id] + 0.04 else AttendanceStatus.absent)
                    db.add(AttendanceRecord(course_id=c.id, student_id=s.id, class_date=day, status=st, marked_by=c.faculty_id))

        # assignments: some past due (graded), some upcoming
        now = datetime.now(timezone.utc)
        for c in courses:
            for k, title in enumerate(ASSIGNMENTS):
                due = now + timedelta(days=(k - 1) * 10 + 3)  # -7, +3, +13 days
                a = Assignment(course_id=c.id, title=title, description=f"{title} for {c.code}", due_date=due,
                               max_marks=50 if k == 2 else 100, created_by=c.faculty_id)
                db.add(a)
                db.flush()
                for s in enrolled[c.id]:
                    if random.random() < (0.9 if due < now else 0.35):
                        graded = due < now
                        db.add(Submission(
                            assignment_id=a.id, student_id=s.id, content=f"Solution by {s.roll_number} for {title}",
                            submitted_at=min(now, due) - timedelta(hours=random.randint(1, 60)), is_late=False,
                            marks=round(random.uniform(0.5, 1.0) * float(a.max_marks), 1) if graded else None,
                            feedback="Well done." if graded else None, graded_by=c.faculty_id if graded else None))
        db.commit()
        print("Seeded: 1 admin, 4 faculty, 30 students, 6 courses, attendance, assignments, submissions.")
        print("Logins: admin@educore.edu | anita.deshmukh@educore.edu | student01@educore.edu  (password = SEED_DEFAULT_PASSWORD)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
