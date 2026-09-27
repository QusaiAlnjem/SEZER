from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field


SOStatus = Literal["open", "partial", "paid", "cancelled"]
PayMethod = Literal["cash", "bank", "remittance", "other"]


class SalesOrderItemIn(BaseModel):
    inventory_item_id: UUID
    qty: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


class SalesOrderItemOut(SalesOrderItemIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    line_total: Decimal
    item_name: Optional[str] = None
    # product identity, so an invoice can print it without a second lookup
    reference: Optional[str] = None
    quality: Optional[str] = None
    shade: Optional[str] = None
    color: Optional[str] = None
    unit: Optional[str] = None


class SalesOrderCreate(BaseModel):
    customer_id: UUID
    order_date: date
    notes: Optional[str] = None
    items: List[SalesOrderItemIn] = Field(min_length=1)
    discount: Decimal = Field(default=Decimal("0"), ge=0)   # الخصم, off the products total


class PaymentIn(BaseModel):
    sales_order_id: UUID
    paid_at: date
    amount: Decimal = Field(gt=0)
    method: PayMethod = "cash"
    notes: Optional[str] = None


class PaymentAllocation(BaseModel):
    """Part of one handover, going to one invoice."""
    sales_order_id: UUID
    amount: Decimal = Field(gt=0)


class PaymentBatchIn(BaseModel):
    """One sum split across several invoices, applied all or nothing.

    A customer hands over a round amount that rarely matches a single
    invoice; this records where each part of it went in one write, so the
    money can never land half-applied.
    """
    paid_at: date
    method: PayMethod = "cash"
    notes: Optional[str] = None
    allocations: List[PaymentAllocation] = Field(min_length=1)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sales_order_id: UUID
    customer_id: UUID
    paid_at: date
    amount: Decimal
    method: PayMethod
    notes: Optional[str] = None


class SalesOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    order_number: str
    customer_id: UUID
    customer_name: Optional[str] = None
    order_date: date
    items_total: Decimal = Decimal("0")   # before the discount
    discount: Decimal = Decimal("0")
    subtotal: Decimal                     # billed, net of the discount
    paid_amount: Decimal
    outstanding: Decimal
    status: SOStatus
    notes: Optional[str] = None
    created_at: datetime
    items: List[SalesOrderItemOut] = []
    payments: List[PaymentOut] = []


class InvoiceItem(BaseModel):
    """One printed line. Product details stay exactly as stored — untranslated."""
    reference: Optional[str] = None
    quality: Optional[str] = None
    shade: Optional[str] = None
    color: Optional[str] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    qty: Decimal
    unit_price: Decimal
    line_total: Decimal


class InvoicePayment(BaseModel):
    """A payment received against this invoice."""
    paid_at: date
    amount: Decimal
    method: PayMethod


class StatementOrder(BaseModel):
    """One invoice inside the statement window."""
    order_number: str
    order_date: date
    subtotal: Decimal
    paid_amount: Decimal
    outstanding: Decimal
    fully_paid: bool


class StatementPayment(BaseModel):
    paid_at: date
    amount: Decimal
    method: PayMethod
    order_number: Optional[str] = None


class StatementProduct(BaseModel):
    """A most-bought line, ranked by quantity over the window."""
    label: str
    unit: Optional[str] = None
    qty: Decimal
    spent: Decimal


class StatementOut(BaseModel):
    id: UUID
    statement_number: str
    issued_at: datetime
    period_from: date
    period_to: date
    customer_name: str
    customer_phone: Optional[str] = None
    customer_city: Optional[str] = None

    orders: List[StatementOrder] = []
    period_invoiced: Decimal        # billed within the window
    period_paid: Decimal            # payments received within the window
    period_outstanding: Decimal     # still due on the listed invoices

    payments: List[StatementPayment] = []
    top_products: List[StatementProduct] = []

    # Everything still owed, invoices older than the window included — so the
    # figure the customer reads is the real debt, not just the period's slice.
    total_outstanding: Decimal
    older_outstanding: Decimal      # total_outstanding − period_outstanding


class InvoiceOut(BaseModel):
    order_number: str
    order_date: date
    issued_at: datetime
    customer_name: str
    customer_phone: Optional[str] = None
    customer_city: Optional[str] = None
    items: List[InvoiceItem] = []
    items_total: Decimal           # products, before the discount
    discount: Decimal              # الخصم
    subtotal: Decimal              # billed, net of the discount
    payments: List[InvoicePayment] = []
    paid_amount: Decimal           # paid against this invoice
    outstanding: Decimal           # still due on this invoice
    previous_balance: Decimal      # unpaid across the customer's other invoices
    grand_total: Decimal           # outstanding + previous_balance
