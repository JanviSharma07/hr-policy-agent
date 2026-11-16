"""Adds the sample employees below to your database (PostgreSQL on your laptop).
Safe to run more than once: an employee who already exists is updated, not duplicated.

Run from the backend folder, with the venv active:
    python add_employees.py

Edit the EMPLOYEES list to use your own names. Everyone gets the password below."""
from datetime import date
from app.db.database import Base, engine, SessionLocal
from app.db import models  # noqa: F401  (registers the tables)
from app.db.models import User
from app.db.migrate import run_migrations
from app.auth.security import hash_password

PASSWORD = "Emp123"

EMPLOYEES = [
    {"email": "ted@company.com", "department": "Engineering", "job_title": "Solutions Architect",
     "grade": "L5", "city": "Bengaluru", "join_date": date(2022, 9, 19),
     "skills": ["System design", "Architecture", "Python"]},
    {"email": "barney@company.com", "department": "Sales", "job_title": "Senior Sales Manager",
     "grade": "L6", "city": "Mumbai", "join_date": date(2020, 2, 3),
     "skills": ["Negotiation", "Client relations", "Presentations"]},
    {"email": "robin@company.com", "department": "Marketing", "job_title": "Communications Manager",
     "grade": "L4", "city": "Mumbai", "join_date": date(2023, 6, 12),
     "skills": ["Public speaking", "Media relations", "Content"]},
    {"email": "lily@company.com", "department": "Human Resources", "job_title": "Learning & Development Specialist",
     "grade": "L3", "city": "Bengaluru", "join_date": date(2024, 1, 8),
     "skills": ["Training", "Onboarding", "Coaching"]},
    {"email": "marshall@company.com", "department": "Legal", "job_title": "Legal Counsel",
     "grade": "L5", "city": "Pune", "join_date": date(2021, 4, 5),
     "skills": ["Contract law", "Compliance", "Negotiation"]},
    {"email": "tracy@company.com", "department": "Finance", "job_title": "Financial Analyst",
     "grade": "L2", "city": "Bengaluru", "join_date": date(2026, 8, 3),
     "skills": ["Excel", "Budgeting", "Economics"]},
]

Base.metadata.create_all(bind=engine)
run_migrations(engine)  # adds department / job_title / skills if the backend hasn't run yet

with SessionLocal() as db:
    for emp in EMPLOYEES:
        user = db.query(User).filter(User.email == emp["email"]).first()
        if user:
            for field, value in emp.items():
                setattr(user, field, value)
            print(f"updated  {emp['email']:<22} {emp['department']}")
        else:
            db.add(User(**emp, role="employee", password_hash=hash_password(PASSWORD)))
            print(f"added    {emp['email']:<22} {emp['department']}")
    db.commit()

print(f"\nDone. Each new employee can sign in with password {PASSWORD}.")
