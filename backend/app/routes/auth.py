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


class RegisterRequest(BaseModel):
    email: str
    password: str
    join_date: date | None = None   # format: YYYY-MM-DD
    grade: str | None = None        # e.g. L3
    city: str | None = None


class ProfileUpdate(BaseModel):
    join_date: date | None = None
    grade: str | None = None
    city: str | None = None


def _user_out(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "join_date": user.join_date,
        "grade": user.grade,
        "city": user.city,
    }


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
        grade=body.grade,
        city=body.city,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(user.id, user.role)
    return {"access_token": token, "token_type": "bearer", "role": user.role}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _user_out(user)


@router.patch("/me")
def update_profile(body: ProfileUpdate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    # Only the fields sent in the request are changed
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return _user_out(user)
