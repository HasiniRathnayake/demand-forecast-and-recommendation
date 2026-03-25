-- setup_supplier_users.sql
-- Adds supplier account mapping to users for supplier portal login.

ALTER TABLE IF EXISTS public.users
ADD COLUMN IF NOT EXISTS supplier_id TEXT REFERENCES public.suppliers(supplier_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_users_supplier_id ON public.users(supplier_id);
