"""Reusable column types."""
import uuid
from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID


def pk_uuid():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at():
    return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


CURRENCIES = ("USD", "SYP")
