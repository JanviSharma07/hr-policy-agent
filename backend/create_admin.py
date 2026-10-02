import sys
from app.db.database import SessionLocal, Base, engine
from app.db import models  # noqa: F401
from app.db.models import User
from app.auth.security import hash_password

if len(sys.argv) != 3:
    print("Usage: python create_admin.py <email> <password>")
    sys.exit(1)

email, password = sys.argv[1], sys.argv[2]
Base.metadata.create_all(bind=engine)

db = SessionLocal()
if db.query(User).filter(User.email == email).first():
    print(f"{email} already exists")
else:
    db.add(User(email=email, password_hash=hash_password(password), role="hr_admin"))
    db.commit()
    print(f"HR admin {email} created")
db.close()