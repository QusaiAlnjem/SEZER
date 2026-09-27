from sqlalchemy import Column, String, Text
from app.database import Base
from app.models._common import pk_uuid, created_at


class Customer(Base):
    __tablename__ = "customers"

    id = pk_uuid()
    name = Column(String, nullable=False)
    phone = Column(String)
    city = Column(String)
    notes = Column(Text)
    created_at = created_at()
