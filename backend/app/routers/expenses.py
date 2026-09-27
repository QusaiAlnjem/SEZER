from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Expense
from app.schemas import ExpenseIn, ExpenseOut
from app.services.auth import get_current_user
from app.services.fx import resolve_fx

router = APIRouter(prefix="/api/expenses", tags=["expenses"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ExpenseOut])
def list_expenses(db: Session = Depends(get_db)):
    return db.query(Expense).order_by(Expense.spent_at.desc()).all()


@router.post("", response_model=ExpenseOut)
def create_expense(body: ExpenseIn, db: Session = Depends(get_db)):
    fx = resolve_fx(db, body.currency, body.fx_to_usd, on_day=body.spent_at)
    row = Expense(**body.model_dump(exclude={"fx_to_usd"}), fx_to_usd=fx)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{eid}")
def delete_expense(eid: UUID, db: Session = Depends(get_db)):
    row = db.get(Expense, eid)
    if not row:
        raise HTTPException(404, "Expense not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
