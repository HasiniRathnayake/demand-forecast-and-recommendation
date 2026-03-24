-- setup_suppliers.sql
-- Enables Supplier Management & Auto-PO Generation in the Stock Replenishment Module

-- 1. Create the Suppliers table
CREATE TABLE IF NOT EXISTS public.suppliers (
    supplier_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    contact_email TEXT,
    phone TEXT,
    lead_time_days INTEGER DEFAULT 7,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Turn off Row Level Security so the Streamlit app can read/write without user-specific policies
ALTER TABLE public.suppliers DISABLE ROW LEVEL SECURITY;

-- Insert some default/demo suppliers
INSERT INTO public.suppliers (name, contact_email, phone, lead_time_days)
VALUES 
    ('Sunrise Global Distributors', 'orders@sunriseglobal.com', '+965 1234 5678', 3),
    ('Kuwait Fresh Produce Co.', 'sales@kfresh.kw', '+965 9876 5432', 1),
    ('Al-Watan FMCG Supplies', 'distribution@alwatan.com', '+965 5544 3322', 5);

-- 2. Create the Purchase Orders table
CREATE TABLE IF NOT EXISTS public.purchase_orders (
    po_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    replenishment_order_id UUID REFERENCES public.replenishment_orders(order_id) ON DELETE CASCADE,
    supplier_id UUID REFERENCES public.suppliers(supplier_id) ON DELETE SET NULL,
    status TEXT DEFAULT 'PENDING_DISPATCH', -- PENDING_DISPATCH, SENT, DELIVERED
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Turn off Row Level Security
ALTER TABLE public.purchase_orders DISABLE ROW LEVEL SECURITY;
