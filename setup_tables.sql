-- ═══════════════════════════════════════════════════════════════
-- Sunrise Super — New Supabase Tables Setup
-- Run this SQL in your Supabase SQL Editor to create the 5 new
-- tables for the team member dashboards.
-- ═══════════════════════════════════════════════════════════════

-- ── 01. Demand Forecasting ── demand_forecasts ───────────────────
CREATE TABLE IF NOT EXISTS demand_forecasts (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  sku           TEXT NOT NULL,
  product_name  TEXT,
  week_start    DATE NOT NULL,
  predicted_qty INTEGER NOT NULL DEFAULT 0,
  actual_qty    INTEGER,
  holiday_flag  BOOLEAN DEFAULT false,
  notes         TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- ── 01. Demand Forecasting ── demand_holidays ────────────────────
CREATE TABLE IF NOT EXISTS demand_holidays (
  id        UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name      TEXT NOT NULL,
  date      DATE NOT NULL,
  impact    TEXT DEFAULT 'MEDIUM' CHECK (impact IN ('HIGH','MEDIUM','LOW')),
  notes     TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ── 02. Waste Monitor ── waste_records ───────────────────────────
CREATE TABLE IF NOT EXISTS waste_records (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  sku           TEXT NOT NULL,
  product_name  TEXT,
  date          DATE NOT NULL,
  waste_qty     INTEGER NOT NULL DEFAULT 0,
  unit_cost_kwd NUMERIC(10,3),
  forecast_qty  INTEGER,
  actual_qty    INTEGER,
  waste_reason  TEXT DEFAULT 'Expired'
                  CHECK (waste_reason IN ('Expired','Damaged','Overstock','Quality Issue','Other')),
  notes         TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- ── 03. Short-Shipment Detector ── shipment_records ──────────────
CREATE TABLE IF NOT EXISTS shipment_records (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  delivery_date   DATE NOT NULL,
  po_number       TEXT NOT NULL,
  supplier        TEXT NOT NULL,
  sku             TEXT,
  product_name    TEXT,
  ordered_qty     INTEGER NOT NULL DEFAULT 0,
  invoiced_qty    INTEGER,
  received_qty    INTEGER NOT NULL DEFAULT 0,
  unit_cost_kwd   NUMERIC(10,3),
  status          TEXT DEFAULT 'OK' CHECK (status IN ('OK','SHORT','RESOLVED')),
  notes           TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- ── 04. Loyalty Manager ── promotions ────────────────────────────
CREATE TABLE IF NOT EXISTS promotions (
  id                UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name              TEXT NOT NULL,
  segment           TEXT DEFAULT 'ALL'
                      CHECK (segment IN ('HIGH_VALUE','REGULAR','AT_RISK','NEW','ALL')),
  discount_pct      NUMERIC(5,2) DEFAULT 0,
  channel           TEXT DEFAULT 'EMAIL'
                      CHECK (channel IN ('EMAIL','SMS','APP','ALL')),
  status            TEXT DEFAULT 'SCHEDULED'
                      CHECK (status IN ('ACTIVE','SCHEDULED','PAUSED','ENDED')),
  start_date        DATE,
  end_date          DATE,
  target_customers  INTEGER DEFAULT 0,
  offer_description TEXT,
  created_at        TIMESTAMPTZ DEFAULT now()
);

-- ── 04. Loyalty Manager ── customer_segments ─────────────────────
CREATE TABLE IF NOT EXISTS customer_segments (
  id                 UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  segment            TEXT NOT NULL
                       CHECK (segment IN ('HIGH_VALUE','REGULAR','AT_RISK','NEW')),
  customer_count     INTEGER DEFAULT 0,
  avg_spend_kwd      NUMERIC(10,3),
  last_purchase_date DATE,
  created_at         TIMESTAMPTZ DEFAULT now()
);

-- ── 05. Inventory Intake ── intake_records ───────────────────────
CREATE TABLE IF NOT EXISTS intake_records (
  id                   UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  sku                  TEXT NOT NULL,
  product_name         TEXT,
  supplier             TEXT,
  po_number            TEXT,
  intake_date          DATE NOT NULL,
  expected_qty         INTEGER NOT NULL DEFAULT 0,
  received_qty         INTEGER NOT NULL DEFAULT 0,
  is_anomaly           BOOLEAN DEFAULT false,
  investigation_status TEXT DEFAULT 'OPEN' CHECK (investigation_status IN ('OPEN','RESOLVED')),
  recorded_by          TEXT,
  notes                TEXT,
  created_at           TIMESTAMPTZ DEFAULT now()
);

-- ── Row Level Security (optional — disables RLS for public access)
ALTER TABLE demand_forecasts   DISABLE ROW LEVEL SECURITY;
ALTER TABLE demand_holidays    DISABLE ROW LEVEL SECURITY;
ALTER TABLE waste_records      DISABLE ROW LEVEL SECURITY;
ALTER TABLE shipment_records   DISABLE ROW LEVEL SECURITY;
ALTER TABLE promotions         DISABLE ROW LEVEL SECURITY;
ALTER TABLE customer_segments  DISABLE ROW LEVEL SECURITY;
ALTER TABLE intake_records     DISABLE ROW LEVEL SECURITY;

-- ── Sample seed data (optional — uncomment to run)
-- INSERT INTO demand_holidays (name, date, impact) VALUES
--   ('Ramadan Start', '2025-03-01', 'HIGH'),
--   ('EId Al-Fitr',   '2025-03-30', 'HIGH'),
--   ('National Day',  '2025-02-25', 'MEDIUM');
