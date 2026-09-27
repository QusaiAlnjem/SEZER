from sqlalchemy import (
    Column,
    String,
    Date,
    DateTime,
    Numeric,
    Boolean,
    ForeignKey,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.database import Base
from app.models._common import pk_uuid, created_at


class Supplier(Base):
    __tablename__ = "suppliers"

    id = pk_uuid()
    name = Column(String, nullable=False)            # الاسم
    company_name = Column(String)                    # اسم الشركة
    phones = Column(ARRAY(String), nullable=False, server_default="{}")  # رقم/أرقام الهاتف
    email = Column(String)
    created_at = created_at()

    orders = relationship(
        "SupplierOrder",
        back_populates="supplier",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SupplierOrder(Base):
    __tablename__ = "supplier_orders"

    id = pk_uuid()
    order_number = Column(String, unique=True, nullable=False)
    supplier_id = Column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_date = Column(Date, nullable=False)
    shipping_date = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="waiting")   # waiting | shipped
    shipped_at = Column(DateTime(timezone=True))
    # What the shipment cost, in USD. `shipment_cost` is the goods total; the
    # two logistics lines are each a flat amount or a percentage of it. These
    # never feed item cost or per-line receipt costs, which have their own
    # numbers — but they do count as spending on the dashboard.
    shipment_cost = Column(Numeric(14, 2))                 # تكلفة البضاعة
    shipping_value = Column(Numeric(14, 2), nullable=False, server_default="0")    # تكلفة الشحن
    shipping_is_percent = Column(Boolean, nullable=False, server_default="false")
    customs_value = Column(Numeric(14, 2), nullable=False, server_default="0")     # تكلفة الجمركة
    customs_is_percent = Column(Boolean, nullable=False, server_default="false")
    created_at = created_at()

    supplier = relationship("Supplier", back_populates="orders")
    products = relationship(
        "SupplierOrderProduct",
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("status IN ('waiting','shipped')", name="supplier_order_status_ck"),
    )


class SupplierOrderProduct(Base):
    """What was ordered. Every field is optional — an order can be placed
    before the details are known."""

    __tablename__ = "supplier_order_products"

    id = pk_uuid()
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("supplier_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String)       # الاسم
    quality = Column(String)    # رقم الطراز
    color = Column(String)      # اللون
    shade = Column(String)      # رقم الطيف

    order = relationship("SupplierOrder", back_populates="products")
