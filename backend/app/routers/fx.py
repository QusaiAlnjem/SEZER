from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FxRate
from app.schemas import FxIn, FxOut
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/fx", tags=["fx"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[FxOut])
def list_rates(db: Session = Depends(get_db)):
    return db.query(FxRate).order_by(FxRate.day.desc()).limit(90).all()


@router.post("", response_model=FxOut)
def upsert_rate(body: FxIn, db: Session = Depends(get_db)):
    existing = db.query(FxRate).filter(FxRate.day == body.day).first()
    if existing:
        existing.syp_per_usd = body.syp_per_usd
        existing.source = body.source
        db.commit()
        db.refresh(existing)
        return existing
    row = FxRate(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
