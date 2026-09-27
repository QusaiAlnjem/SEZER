from sqlalchemy import Column, Date, Numeric, String, BigInteger
from app.database import Base


class FxRate(Base):
    __tablename__ = "fx_rates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    day = Column(Date, unique=True, nullable=False)
    syp_per_usd = Column(Numeric(14, 4), nullable=False)
    source = Column(String, default="manual")
