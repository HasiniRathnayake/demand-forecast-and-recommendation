-- setup_apriori_rules.sql
-- Stores precomputed Apriori association rules in Supabase.

CREATE TABLE IF NOT EXISTS public.association_rules (
    rule_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    antecedent_product_code TEXT NOT NULL,
    consequent_product_code TEXT NOT NULL,
    support DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    lift DOUBLE PRECISION NOT NULL,
    last_updated DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE (antecedent_product_code, consequent_product_code)
);

ALTER TABLE public.association_rules DISABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_association_rules_antecedent
    ON public.association_rules(antecedent_product_code);

CREATE INDEX IF NOT EXISTS idx_association_rules_consequent
    ON public.association_rules(consequent_product_code);