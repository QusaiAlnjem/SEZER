from sqlalchemy import Column, String, Text, Date, Numeric, CheckConstraint
from app.database import Base
from app.models._common import pk_uuid


class Expense(Base):
    __tablename__ = "expenses"

    id = pk_uuid()
    category = Column(String, nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String, nullable=False)
    fx_to_usd = Column(Numeric(14, 4), nullable=False)
    spent_at = Column(Date, nullable=False)
    notes = Column(Text)

    __table_args__ = (
        CheckConstraint("currency IN ('USD','SYP')", name="exp_currency_ck"),
    )
