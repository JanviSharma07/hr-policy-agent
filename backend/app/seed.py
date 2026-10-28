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
    {"email": "hr@company.com", "password": "Admin123", "role": "hr_admin"},
    {"email": "emp@company.com", "password": "Emp123", "role": "employee",
     "join_date": date(2026, 3, 2), "grade": "L3", "city": "Bengaluru"},
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
        if not db.query(User).filter(User.email == u["email"]).first():
            db.add(User(**{k: v for k, v in u.items() if k != "password"},
                        password_hash=hash_password(u["password"])))
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
