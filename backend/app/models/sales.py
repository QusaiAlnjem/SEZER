from sqlalchemy import (
    Column,
    String,
    Text,
    Date,
    Numeric,
    ForeignKey,
    CheckConstraint,
    Computed,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.models._common import pk_uuid, created_at


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = pk_uuid()
    order_number = Column(String, unique=True, nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    order_date = Column(Date, nullable=False)
    # Knocked off the products total. `subtotal` is what is actually billed,
    # already net of it, so payments and balances need no special case.
    discount = Column(Numeric(14, 2), nullable=False, default=0)
    subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    paid_amount = Column(Numeric(14, 2), nullable=False, default=0)
    status = Column(String, nullable=False, default="open")
    notes = Column(Text)
    created_at = created_at()

    customer = relationship("Customer")
    items = relationship(
        "SalesOrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    payments = relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Amounts are USD throughout, so there is no currency or fx to carry.
    __table_args__ = (
        CheckConstraint(
            "status IN ('open','partial','paid','cancelled')", name="so_status_ck"
        ),
    )


class SalesOrderItem(Base):
    __tablename__ = "sales_order_items"

    id = pk_uuid()
    sales_order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sales_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    inventory_item_id = Column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False
    )
    qty = Column(Numeric(14, 3), nullable=False)
    unit_price = Column(Numeric(14, 4), nullable=False)
    line_total = Column(
        Numeric(14, 2), Computed("qty * unit_price", persisted=True)
    )

    order = relationship("SalesOrder", back_populates="items")
    item = relationship("InventoryItem")


class AccountStatement(Base):
    """A كشف حساب issued to a customer, covering one year up to its issue date.

    Only the identity and the window are stored — the figures are recomputed
    from orders and payments each time it is opened, the same way an invoice is.
    """

    __tablename__ = "account_statements"

    id = pk_uuid()
    statement_number = Column(String, unique=True, nullable=False)
    customer_id = Column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    period_from = Column(Date, nullable=False)
    period_to = Column(Date, nullable=False)
    created_at = created_at()

    customer = relationship("Customer")


class Payment(Base):
    __tablename__ = "payments"

    id = pk_uuid()
    sales_order_id = Column(
        UUID(as_uuid=True), ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False
    )
    customer_id = Column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    paid_at = Column(Date, nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    method = Column(String, default="cash")
    notes = Column(Text)

    order = relationship("SalesOrder", back_populates="payments")
    customer = relationship("Customer")

    __table_args__ = (
        CheckConstraint(
            "method IN ('cash','bank','remittance','other')", name="pay_method_ck"
        ),
    )
