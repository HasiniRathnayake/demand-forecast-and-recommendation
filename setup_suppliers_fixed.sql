-- setup_suppliers_fixed.sql
-- Enables Supplier Management & Auto-PO Generation in the Stock Replenishment Module

-- 1. Create the Suppliers table (Only if it doesn't already exist from the teammates' modules)
CREATE TABLE IF NOT EXISTS public.suppliers (
    supplier_id TEXT PRIMARY KEY,
    supplier_name TEXT NOT NULL,
    email TEXT,
    contact_number TEXT
);

-- Turn off Row Level Security so the Streamlit app can read/write without user-specific policies
ALTER TABLE public.suppliers DISABLE ROW LEVEL SECURITY;

-- Insert some default/demo suppliers using the EXACT schema your teammates already created
INSERT INTO public.suppliers (supplier_id, supplier_name, email, contact_number)
VALUES 
    ('SUP-002', 'Sunrise Global Distributors', 'orders@sunriseglobal.com', '+965 1234 5678'),
    ('SUP-003', 'Kuwait Fresh Produce Co.', 'sales@kfresh.kw', '+965 9876 5432'),
    ('SUP-004', 'Al-Watan FMCG Supplies', 'distribution@alwatan.com', '+965 5544 3322')
ON CONFLICT (supplier_id) DO NOTHING;

-- 2. Create the Purchase Orders table mapped to the existing Supplier table
CREATE TABLE IF NOT EXISTS public.purchase_orders (
    po_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    replenishment_order_id TEXT REFERENCES public.replenishment_orders(order_id) ON DELETE CASCADE,
    supplier_id TEXT REFERENCES public.suppliers(supplier_id) ON DELETE SET NULL,
    status TEXT DEFAULT 'PENDING_DISPATCH', -- PENDING_DISPATCH, SENT, DELIVERED
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Turn off Row Level Security
ALTER TABLE public.purchase_orders DISABLE ROW LEVEL SECURITY;
