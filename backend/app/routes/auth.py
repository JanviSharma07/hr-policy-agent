from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User
from app.auth.security import hash_password, verify_password, create_access_token
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

# Departments offered in the sign-up form and the HR employee editor
DEPARTMENTS = ["Engineering", "Sales", "Marketing", "Finance", "Human Resources", "Operations", "Customer Support", "Legal"]


class RegisterRequest(BaseModel):
    email: str
    password: str
    join_date: date | None = None   # format: YYYY-MM-DD
    department: str | None = None
    job_title: str | None = None
    city: str | None = None


class ProfileUpdate(BaseModel):
    # What an employee can change about themselves.
    # Department, joining date and grade are managed by HR (see routes/hr.py).
    job_title: str | None = None
    city: str | None = None
    skills: list[str] | None = None


def clean_skills(skills: list[str] | None) -> list[str] | None:
    """Trims, removes blanks and duplicates (case-insensitive), keeps the first 15."""
    if skills is None:
        return None
    seen, out = set(), []
    for s in skills:
        s = (s or "").strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s[:40])
    return out[:15]


def user_out(user: User, include_grade: bool = False) -> dict:
    """The grade decides travel entitlements, so the agents use it, but it is only shown to HR."""
    data = {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "join_date": user.join_date,
        "department": user.department,
        "job_title": user.job_title,
        "skills": user.skills or [],
        "city": user.city,
    }
    if include_grade:
        data["grade"] = user.grade
    return data


@router.post("/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Self-registration always creates an employee. HR admins are created by script.
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role="employee",
        join_date=body.join_date,
        department=body.department,
        job_title=body.job_title,
        city=body.city,
        skills=[],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(user.id, user.role)
    return {"access_token": token, "token_type": "bearer", "role": user.role}


@router.get("/departments")
def departments():
    return DEPARTMENTS


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user, include_grade=user.role == "hr_admin")


@router.patch("/me")
def update_profile(body: ProfileUpdate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    # Only the fields sent in the request are changed
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "skills":
            value = clean_skills(value)
        elif isinstance(value, str):
            value = value.strip() or None
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user_out(user, include_grade=user.role == "hr_admin")
