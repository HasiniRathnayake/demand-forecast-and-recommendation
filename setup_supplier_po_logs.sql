-- setup_supplier_po_logs.sql
-- Supplier PO Notification & Dashboard Tracking

-- Create supplier_po_logs table for tracking sent POs
CREATE TABLE IF NOT EXISTS public.supplier_po_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    po_id UUID REFERENCES public.purchase_orders(po_id) ON DELETE CASCADE,
    supplier_id UUID REFERENCES public.suppliers(supplier_id) ON DELETE SET NULL,
    product_code VARCHAR(50),
    quantity INTEGER,
    order_date TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    expected_delivery_date DATE,
    email_sent BOOLEAN DEFAULT FALSE,
    email_sent_at TIMESTAMP WITH TIME ZONE,
    email_address TEXT,
    sent_by TEXT, -- Username/admin who sent the PO
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Turn off Row Level Security
ALTER TABLE public.supplier_po_logs DISABLE ROW LEVEL SECURITY;

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_supplier_po_logs_supplier_id 
ON public.supplier_po_logs(supplier_id);

CREATE INDEX IF NOT EXISTS idx_supplier_po_logs_po_id 
ON public.supplier_po_logs(po_id);

CREATE INDEX IF NOT EXISTS idx_supplier_po_logs_email_sent 
ON public.supplier_po_logs(email_sent);
