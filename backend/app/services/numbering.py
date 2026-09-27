"""Auto-numbering helpers for Sales Orders, Supplier Orders and Statements.

Format: <PREFIX>-YYYYMM-#### (monthly reset)
"""
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import SalesOrder, SupplierOrder, AccountStatement


def _month_prefix(prefix: str, today: date) -> str:
    return f"{prefix}-{today.strftime('%Y%m')}-"


def next_po_number(db: Session, today: date | None = None) -> str:
    today = today or date.today()
    prefix = _month_prefix("PO", today)
    last = (
        db.query(func.max(SupplierOrder.order_number))
        .filter(SupplierOrder.order_number.like(f"{prefix}%"))
        .scalar()
    )
    n = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{n:04d}"


def next_so_number(db: Session, today: date | None = None) -> str:
    today = today or date.today()
    prefix = _month_prefix("SO", today)
    last = (
        db.query(func.max(SalesOrder.order_number))
        .filter(SalesOrder.order_number.like(f"{prefix}%"))
        .scalar()
    )
    n = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{n:04d}"


def next_statement_number(db: Session, today: date | None = None) -> str:
    today = today or date.today()
    prefix = _month_prefix("ST", today)
    last = (
        db.query(func.max(AccountStatement.statement_number))
        .filter(AccountStatement.statement_number.like(f"{prefix}%"))
        .scalar()
    )
    n = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{n:04d}"
