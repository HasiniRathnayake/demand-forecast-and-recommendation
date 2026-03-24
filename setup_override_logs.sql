-- setup_override_logs.sql
-- Enables Human Override Justification in the Stock Replenishment Module

CREATE TABLE IF NOT EXISTS public.override_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id TEXT REFERENCES public.replenishment_orders(order_id) ON DELETE CASCADE,
    product_code TEXT,
    predicted_quantity INTEGER NOT NULL,
    ordered_quantity INTEGER NOT NULL,
    anomaly_flag BOOLEAN DEFAULT false,
    override_reason TEXT,
    overridden_by TEXT, -- admin username
    overridden_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Turn off Row Level Security so the Streamlit app can reliably insert overrides
ALTER TABLE public.override_logs DISABLE ROW LEVEL SECURITY;
