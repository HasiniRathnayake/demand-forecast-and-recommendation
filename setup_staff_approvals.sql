-- setup_staff_approvals.sql
-- Staff approval workflow table. New staff accounts remain blocked until approved by admin.

CREATE TABLE IF NOT EXISTS public.staff_approvals (
    user_id BIGINT PRIMARY KEY REFERENCES public.users(user_id) ON DELETE CASCADE,
    approval_status TEXT NOT NULL DEFAULT 'pending' CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_staff_approvals_status ON public.staff_approvals(approval_status);
CREATE INDEX IF NOT EXISTS idx_staff_approvals_requested_at ON public.staff_approvals(requested_at);

ALTER TABLE public.staff_approvals DISABLE ROW LEVEL SECURITY;
