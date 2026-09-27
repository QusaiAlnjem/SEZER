# SEZER — Database Schema

PostgreSQL 15+. All monetary amounts stored as `numeric(14,2)`. Every money-carrying row also stores `currency` (`'USD' | 'SYP'`) and, for anything that will feed the dashboard's normalized totals, an `fx_to_usd` snapshot captured at entry time so historical figures don't drift when today's rate changes.

## Tables

### users
Single-user PIN login. One row seeded at first boot.
- `id` uuid pk
- `username` text unique  (default: `'owner'`)
- `pin_hash` text          (bcrypt of the 4–6 digit PIN)
- `created_at` timestamptz default now()

### fx_rates
Daily rate history. Used by the dashboard to convert historical rows into USD for display, but each transaction ALSO stores its own `fx_to_usd` so nothing recomputes silently.
- `id` bigserial pk
- `day` date unique
- `syp_per_usd` numeric(14,4) not null
- `source` text  (`'manual'` or an api slug)

### suppliers
Who we buy from. `phones` is a text[] so a supplier can have several numbers.
- `id` uuid pk
- `name` text not null            الاسم
- `company_name` text             اسم الشركة
- `phones` text[] not null default '{}'
- `email` text
- `created_at` timestamptz default now()

### supplier_photos
Pictures of what a supplier sells, each with its own note.
- `id` uuid pk
- `supplier_id` uuid → suppliers.id on delete cascade
- `storage_path` text not null    (object key in the storage bucket)
- `description` text
- `uploaded_at` timestamptz default now()

### supplier_orders
A purchase order. Starts `waiting`; becomes `shipped` either from the button on
its card, or automatically when a stock receipt is saved against it.
- `id` uuid pk
- `order_number` text unique      (auto: `PO-YYYYMM-####`)
- `supplier_id` uuid → suppliers.id on delete cascade
- `order_date` date not null
- `shipping_date` date not null
- `status` text check in (`'waiting','shipped'`)
- `shipped_at` timestamptz
- `shipment_cost` numeric(14,2)   تكلفة البضاعة — the goods total, null until recorded
- `shipping_value` numeric(14,2) not null default 0 · `shipping_is_percent` bool  تكلفة الشحن
- `customs_value` numeric(14,2) not null default 0 · `customs_is_percent` bool     تكلفة الجمركة
- `created_at` timestamptz default now()

The two logistics columns are each a flat USD amount, or a percentage of
`shipment_cost` when the matching `_is_percent` flag is set. All three are kept
out of item unit costs and receipt lines, which carry their own numbers — but
their sum counts as spending on the dashboard, dated at `shipped_at`. That
overlaps with COGS on purpose: goods bought are costed here *and* again as they
sell. `totals.purchases_usd` keeps the overlapping part visible.

### supplier_order_products
What was ordered — every column optional, since an order can be placed before
the details are settled.
- `id` uuid pk
- `order_id` uuid → supplier_orders.id on delete cascade
- `name` text · `quality` text (رقم الطراز) · `color` text · `shade` text (رقم الطيف)

### customers
- `id` uuid pk
- `name` text not null
- `phone` text
- `city` text
- `notes` text
- `created_at` timestamptz default now()

Views derived from this + sales_orders + payments answer "who paid in full / who still owes".

### sales_orders
"Selling order with the customer name and goods bought from storage and number of units" — this table is where the Creditors page's "make a selling order" button lands.
- `id` uuid pk
- `order_number` text unique  (auto: `SO-YYYYMM-####`)
- `customer_id` uuid → customers.id
- `order_date` date not null default current_date
- `subtotal` numeric(14,2) default 0

Sales are USD-only — there is no `currency`/`fx_to_usd` here or on `payments`.
Expenses and `fx_rates` still carry SYP.
- `paid_amount` numeric(14,2) default 0       (materialized from payments in same currency)
- `status` text check in (`'open','partial','paid','cancelled'`)
- `notes` text
- `created_at` timestamptz default now()

### sales_order_items
Each line decrements `inventory_items.qty_on_hand` at commit time.
- `id` uuid pk
- `sales_order_id` uuid → sales_orders.id on delete cascade
- `inventory_item_id` uuid → inventory_items.id
- `qty` numeric(14,3) not null
- `unit_price` numeric(14,4) not null
- `line_total` numeric(14,2) generated always as (qty * unit_price) stored

### payments
Partial payments allowed; a customer's outstanding = sum(sales_orders.subtotal) - sum(payments.amount) per currency.
- `id` uuid pk
- `sales_order_id` uuid → sales_orders.id
- `customer_id` uuid → customers.id  (denormalized for fast per-customer aggregation)
- `paid_at` date not null default current_date
- `amount` numeric(14,2) not null
- `currency` text check in (`'USD','SYP'`)
- `fx_to_usd` numeric(14,4) not null
- `method` text check in (`'cash','bank','remittance','other'`)
- `notes` text

### inventory_items
Master item list. One row per **shade**: a packing list ships PROD. NO. 121771 as
shades 1..7, and each is stocked, priced and sold on its own while sharing the
reference. Identity is therefore the whole (reference, quality, shade, color)
tuple, enforced by the `uq_inventory_identity` unique index (it COALESCEs the two
nullable halves so NULLs still collide).
- `id` uuid pk
- `reference` text not null       الرقم التعريفي — the mill's PROD. NO. (e.g. `121771`), repeats across shades
- `quality` text not null         رقم الطراز — QUALITY / lot (e.g. `LOT-20`)
- `color` text                    اللون — set when the shade column holds a name (`BLACK`, `NAVY`)
- `shade` text                    رقم الطيف — set only when the shade is a number
- `name` text                     الاسم (optional)
- `unit` text not null default 'm'
- `qty_on_hand` numeric(14,3) default 0
- `avg_unit_cost_usd` numeric(14,4) default 0   (weighted-avg cost, USD-normalized — powers COGS)
- `reorder_level` numeric(14,3) default 100     (not on the form: 100 for length units, 10 for pieces)
- `image_path` text               (object key of the product picture, one per item)
- `created_at` timestamptz default now()

Only `reference`, `quality` and the quantity are required when adding an item.

### inventory_receipts
"Goods received" event. Saving one against a waiting order ships that order.
- `id` uuid pk
- `supplier_order_id` uuid → supplier_orders.id on delete set null
- `received_at` timestamptz default now()
- `notes` text

### inventory_receipt_items
- `id` uuid pk
- `receipt_id` uuid → inventory_receipts.id on delete cascade
- `inventory_item_id` uuid → inventory_items.id
- `qty` numeric(14,3) not null
- `unit_cost` numeric(14,4) not null
- `currency` text check in (`'USD','SYP'`)
- `fx_to_usd` numeric(14,4) not null
- On insert: trigger updates `inventory_items.qty_on_hand` and recomputes `avg_unit_cost_usd`.

### inventory_documents
PDF or Excel evidence uploaded alongside a receipt. Files live in Supabase Storage bucket `inventory-docs`; DB row holds the object path + parsed metadata.
- `id` uuid pk
- `receipt_id` uuid → inventory_receipts.id
- `filename` text
- `mime_type` text
- `storage_path` text            (bucket-relative, e.g. `2026/08/uuid.pdf`)
- `size_bytes` bigint
- `parsed` boolean default false  (true if the Excel importer ingested rows from it)
- `uploaded_at` timestamptz default now()

### expenses
Daily operating expenses (rent, salaries, utilities).
- `id` uuid pk
- `category` text                 (`rent, salary, utility, transport, other`)
- `amount` numeric(14,2) not null
- `currency` text check in (`'USD','SYP'`)
- `fx_to_usd` numeric(14,4) not null
- `spent_at` date default current_date
- `notes` text

## Derived / dashboard queries

Cash flow (per day, USD-normalized):
```sql
SELECT day,
       coalesce(sum(inflow),0)  AS inflow_usd,
       coalesce(sum(outflow),0) AS outflow_usd,
       coalesce(sum(inflow),0) - coalesce(sum(outflow),0) AS net_usd
FROM (
  SELECT paid_at AS day, amount * fx_to_usd AS inflow, 0::numeric AS outflow FROM payments
  UNION ALL
  SELECT spent_at, 0, amount * fx_to_usd FROM expenses
) t
GROUP BY day ORDER BY day;
```

Net margin (period):
```
revenue_usd  = SUM(sales_order_items.qty * unit_price * sales_orders.fx_to_usd)
cogs_usd     = SUM(sales_order_items.qty * inventory_items.avg_unit_cost_usd)
opex_usd     = SUM(expenses.amount * fx_to_usd)
net_margin   = revenue_usd - cogs_usd - opex_usd
```

Outstanding per customer (per currency, so partial cross-currency payments show honestly):
```sql
SELECT c.id, c.name, so.currency,
       SUM(so.subtotal) - COALESCE(SUM(p.amount),0) AS outstanding
FROM customers c
JOIN sales_orders so ON so.customer_id = c.id
LEFT JOIN payments p ON p.sales_order_id = so.id AND p.currency = so.currency
GROUP BY c.id, c.name, so.currency
HAVING SUM(so.subtotal) - COALESCE(SUM(p.amount),0) > 0;
```
