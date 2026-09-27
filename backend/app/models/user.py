from sqlalchemy import Column, String
from app.database import Base
from app.models._common import pk_uuid, created_at


class User(Base):
    __tablename__ = "users"

    id = pk_uuid()
    username = Column(String, unique=True, nullable=False, default="owner")
    pin_hash = Column(String, nullable=False)
    created_at = created_at()
