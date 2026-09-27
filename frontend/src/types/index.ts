export interface Supplier {
  id: string;
  name: string;
  company_name?: string | null;
  phones: string[];
  email?: string | null;
  created_at: string;
  order_count: number;
}

export interface OrderProduct {
  id: string;
  name?: string | null;
  quality?: string | null;
  color?: string | null;
  shade?: string | null;      // رقم الطيف
}

export type OrderStatus = "waiting" | "shipped";

export interface SupplierOrder {
  id: string;
  order_number: string;
  supplier_id: string;
  supplier_name?: string | null;
  supplier_company?: string | null;
  order_date: string;
  shipping_date: string;
  status: OrderStatus;
  shipped_at?: string | null;
  shipment_cost?: string | null;   // تكلفة البضاعة — goods total, USD
  shipping_value: string;          // تكلفة الشحن, flat or % of the goods total
  shipping_is_percent: boolean;
  customs_value: string;           // تكلفة الجمركة
  customs_is_percent: boolean;
  shipping_amount: string;         // resolved by the server
  customs_amount: string;
  total_cost: string;
  created_at: string;
  products: OrderProduct[];
}

export interface OrderPage {
  orders: SupplierOrder[];
  total: number;
  has_more: boolean;
}

export interface Customer {
  id: string;
  name: string;
  phone?: string | null;
  city?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface CustomerBalance {
  customer_id: string;
  customer_name: string;
  phone?: string | null;
  invoiced: string;
  paid: string;
  outstanding: string;
  fully_paid: boolean;
  order_count: number;
  last_order_date?: string | null;
}

export interface InventoryItem {
  id: string;
  reference: string;          // الرقم التعريفي
  quality: string;            // رقم الطراز
  color?: string | null;      // اللون
  shade?: string | null;      // رقم الطيف (numeric shades only)
  name?: string | null;       // الاسم
  unit: string;               // الوحدة
  qty_on_hand: string;        // الكمية المتوفرة
  avg_unit_cost_usd: string;  // تكلفة الوحدة (USD) — what it cost
  selling_price: string;      // سعر البيع — what it sells for
  logistics_per_unit?: string | null;   // shipping + customs share of the unit cost
  reorder_level: string;
  created_at: string;
}

export interface SalesOrderItem {
  id: string;
  inventory_item_id: string;
  item_name?: string | null;
  reference?: string | null;
  quality?: string | null;
  shade?: string | null;
  color?: string | null;
  unit?: string | null;
  qty: string;
  unit_price: string;
  line_total: string;
}

export interface Payment {
  id: string;
  sales_order_id: string;
  customer_id: string;
  paid_at: string;
  amount: string;
  method: "cash" | "bank" | "remittance" | "other";
  notes?: string | null;
}

export interface SalesOrder {
  id: string;
  order_number: string;
  customer_id: string;
  customer_name?: string | null;
  order_date: string;
  items_total: string;      // before the discount
  discount: string;
  subtotal: string;         // billed, net of the discount
  paid_amount: string;
  outstanding: string;
  status: "open" | "partial" | "paid" | "cancelled";
  notes?: string | null;
  created_at: string;
  items: SalesOrderItem[];
  payments: Payment[];
}

/** Outcome of parsing a packing list. The file itself is never stored. */
export interface ImportResult {
  filename: string;
  rows_found: number;
  imported: number;
  skipped: number;
}

export interface SeriesPoint {
  bucket: string;
  label: string;
  earnings_usd: string;
  spending_usd: string;
  profit_usd: string;
}

export interface ProductSales {
  inventory_item_id: string;
  label: string;
  unit: string;
  qty_sold: string;
  revenue_usd: string;
}

export interface CustomerBrief {
  id: string;
  name: string;
  phone?: string | null;
  city?: string | null;
}

export interface DashboardData {
  today: {
    date: string;
    inflow_usd: string;
    outflow_usd: string;
    net_usd: string;
    expenses_usd: string;
  };
  totals: {
    period_from: string;
    period_to: string;
    revenue_usd: string;
    cogs_usd: string;
    opex_usd: string;
    purchases_usd: string;
    net_margin_usd: string;
    net_margin_pct: number | null;
    open_so_count: number;
    outstanding_ar_usd: string;
    low_stock_count: number;
  };
  series: SeriesPoint[];
  granularity: "day" | "month";
  range_from: string;
  range_to: string;
  has_earlier: boolean;
  top_products: ProductSales[];
  slow_products: ProductSales[];
  customers_this_month: number;
  sample_customers: CustomerBrief[];
  fx_syp_per_usd: string;
}
