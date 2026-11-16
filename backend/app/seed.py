"""Demo set-up for the hosted version: creates the test accounts and loads the sample
policies when the database is empty. Runs only when SEED_DEMO=1 (set in the Dockerfile),
so it never touches the local PostgreSQL database."""
import logging
import os
import shutil
from datetime import date
from pathlib import Path
from uuid import uuid4

from app.auth.security import hash_password
from app.config import BASE_DIR, UPLOAD_DIR
from app.db.models import Document, User
from app.ingestion.pipeline import prepare_document
from app.retrieval.vector_store import add_chunks, sync_document_chunks

log = logging.getLogger("uvicorn.error")
SEED_DIR = BASE_DIR / "seed_policies"

USERS = [
    {"email": "hr@company.com", "password": "Admin123", "role": "hr_admin",
     "department": "Human Resources", "job_title": "HR Manager", "city": "Bengaluru",
     "skills": ["Policy drafting", "Employee relations", "Payroll"]},
    {"email": "emp@company.com", "password": "Emp123", "role": "employee",
     "join_date": date(2026, 3, 2), "grade": "L3", "city": "Bengaluru",
     "department": "Engineering", "job_title": "Software Engineer",
     "skills": ["Python", "React", "SQL"]},
    # Extra employees so the HR directory and insights have something to show
    {"email": "ted@company.com", "password": "Emp123", "role": "employee",
     "department": "Engineering", "job_title": "Solutions Architect",
     "grade": "L5", "city": "Bengaluru", "join_date": date(2022, 9, 19),
     "skills": ["System design", "Architecture", "Python"]},
    {"email": "barney@company.com", "password": "Emp123", "role": "employee",
     "department": "Sales", "job_title": "Senior Sales Manager",
     "grade": "L6", "city": "Mumbai", "join_date": date(2020, 2, 3),
     "skills": ["Negotiation", "Client relations", "Presentations"]},
    {"email": "robin@company.com", "password": "Emp123", "role": "employee",
     "department": "Marketing", "job_title": "Communications Manager",
     "grade": "L4", "city": "Mumbai", "join_date": date(2023, 6, 12),
     "skills": ["Public speaking", "Media relations", "Content"]},
    {"email": "lily@company.com", "password": "Emp123", "role": "employee",
     "department": "Human Resources", "job_title": "Learning & Development Specialist",
     "grade": "L3", "city": "Bengaluru", "join_date": date(2024, 1, 8),
     "skills": ["Training", "Onboarding", "Coaching"]},
    {"email": "marshall@company.com", "password": "Emp123", "role": "employee",
     "department": "Legal", "job_title": "Legal Counsel",
     "grade": "L5", "city": "Pune", "join_date": date(2021, 4, 5),
     "skills": ["Contract law", "Compliance", "Negotiation"]},
    {"email": "tracy@company.com", "password": "Emp123", "role": "employee",
     "department": "Finance", "job_title": "Financial Analyst",
     "grade": "L2", "city": "Bengaluru", "join_date": date(2026, 8, 3),
     "skills": ["Excel", "Budgeting", "Economics"]},
]

# (file, title, version). A second row with the same title uploads a newer version,
# so the old one is archived exactly as "Replace" does in Manage policies.
POLICIES = [
    ("Leave_Policy_2026.pdf", "Leave Policy", "2026"),
    ("Travel_Reimbursement_Policy.docx", "Travel Policy", "2026"),
    ("Travel_Reimbursement_Policy_2027.docx", "Travel Policy", "2027"),
    ("WFH_Policy_2025.pdf", "WFH Policy", "2025"),
    ("WFH_Policy_2026.pdf", "WFH Policy", "2026"),
    ("Holiday_Policy_2026.pdf", "Holiday Policy", "2026"),
    ("Employee_Handbook_2026.pdf", "Employee Handbook", "2026"),
    ("Anti_Harassment_Policy_2026.pdf", "Anti-Harassment Policy", "2026"),
]


def seed_demo(db) -> None:
    if os.getenv("SEED_DEMO") != "1":
        return
    for u in USERS:
        fields = {k: v for k, v in u.items() if k != "password"}
        existing = db.query(User).filter(User.email == u["email"]).first()
        if not existing:
            db.add(User(**fields, password_hash=hash_password(u["password"])))
        elif not existing.department:  # demo accounts made before departments existed
            for k in ("department", "job_title", "skills"):
                setattr(existing, k, fields.get(k))
    db.commit()

    if db.query(Document).count():
        return
    admin = db.query(User).filter(User.role == "hr_admin").first()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    current: dict[str, Document] = {}
    for filename, title, version in POLICIES:
        source = SEED_DIR / filename
        if not source.exists():
            log.warning("Seed policy missing: %s", filename)
            continue
        dest = UPLOAD_DIR / f"{uuid4().hex}{source.suffix}"
        shutil.copy(source, dest)
        old = current.get(title)
        doc = Document(title=title, filename=dest.name, version=version,
                       uploaded_by=admin.id, is_active=True)
        db.add(doc)
        db.flush()
        doc.family_id = old.family_id if old else doc.id
        ids, texts, metas = prepare_document(Path(dest), doc.id, doc.family_id, title, version)
        add_chunks(ids, texts, metas)
        doc.chunk_count = len(ids)
        if old:
            old.is_active = False
        db.commit()
        if old:
            sync_document_chunks(old.id, old.family_id, False)
        current[title] = doc
        log.info("Seeded %s v%s (%d sections)", title, version, len(ids))
