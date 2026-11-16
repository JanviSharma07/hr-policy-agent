"""Company holiday calendar. Everyone can read it; only HR can add or remove holidays.
The 2026 list matches section 6 of the Holiday Policy (version 2026.2)."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Holiday, User
from app.auth.dependencies import get_current_user, require_hr_admin

router = APIRouter(prefix="/holidays", tags=["holidays"])

# Dates from the Government of India list of gazetted holidays for 2026
HOLIDAYS_2026 = [
    (date(2026, 1, 26), "Republic Day", "fixed"),
    (date(2026, 3, 4), "Holi", "fixed"),
    (date(2026, 4, 3), "Good Friday", "fixed"),
    (date(2026, 5, 1), "Buddha Purnima", "fixed"),
    (date(2026, 8, 15), "Independence Day", "fixed"),
    (date(2026, 9, 4), "Janmashtami", "fixed"),
    (date(2026, 10, 2), "Gandhi Jayanti", "fixed"),
    (date(2026, 10, 20), "Dussehra", "fixed"),
    (date(2026, 11, 8), "Diwali (Deepavali)", "fixed"),
    (date(2026, 12, 25), "Christmas Day", "fixed"),
    (date(2026, 3, 21), "Id-ul-Fitr", "optional"),
    (date(2026, 3, 26), "Ram Navami", "optional"),
    (date(2026, 3, 31), "Mahavir Jayanti", "optional"),
    (date(2026, 5, 27), "Id-ul-Zuha (Bakrid)", "optional"),
    (date(2026, 6, 26), "Muharram", "optional"),
    (date(2026, 8, 26), "Milad-un-Nabi", "optional"),
    (date(2026, 11, 24), "Guru Nanak Jayanti", "optional"),
]


class NewHoliday(BaseModel):
    day: date
    name: str
    kind: str = "fixed"  # fixed | optional


def seed_holidays(db: Session) -> None:
    """Fills the calendar on first start. Never touches it again once HR has holidays in it."""
    if db.query(Holiday).count():
        return
    db.add_all(Holiday(day=d, name=n, kind=k) for d, n, k in HOLIDAYS_2026)
    db.commit()


def _out(h: Holiday) -> dict:
    return {"id": h.id, "day": h.day, "name": h.name, "kind": h.kind}


@router.get("")
def list_holidays(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_out(h) for h in db.query(Holiday).order_by(Holiday.day).all()]


@router.post("")
def add_holiday(body: NewHoliday, db: Session = Depends(get_db), _: User = Depends(require_hr_admin)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Holiday name cannot be empty")
    if body.kind not in ("fixed", "optional"):
        raise HTTPException(status_code=400, detail="kind must be fixed or optional")
    if db.query(Holiday).filter(Holiday.day == body.day).first():
        raise HTTPException(status_code=400, detail="There is already a holiday on that date")
    h = Holiday(day=body.day, name=name, kind=body.kind)
    db.add(h)
    db.commit()
    db.refresh(h)
    return _out(h)


@router.delete("/{holiday_id}")
def delete_holiday(holiday_id: int, db: Session = Depends(get_db), _: User = Depends(require_hr_admin)):
    h = db.get(Holiday, holiday_id)
    if h is None:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(h)
    db.commit()
    return {"deleted": holiday_id}
