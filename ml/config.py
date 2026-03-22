"""
Configuration for the Sunrise Super Procurement ML Pipeline
Project: 2026-Y2-S2-KU-AI-02
"""

SUPABASE_URL = "https://obbctmyetrdortxyglle.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9iYmN0bXlldHJkb3J0eHlnbGxlIiwicm9sZSI6"
    "InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTY1OTg1MywiZXhwIjoyMDg3MjM1ODUzfQ."
    "uaOYLnsgpN7R4mcbd4qcd8_jY4swh18Cf8sKF063LOg"
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

TABLE_REPLENISHMENT = "replenishment_orders"

# ML Hyperparameters
N_CLUSTERS          = 4        # K-Means: Fast / Medium / Slow / Dead movers
XGB_N_ESTIMATORS    = 200
XGB_MAX_DEPTH       = 5
XGB_LEARNING_RATE   = 0.05
RF_N_ESTIMATORS     = 150
SAFETY_BUFFER_PCT   = 0.10     # 10% safety buffer on top of optimal level
LEAD_TIME_DAYS      = 7        # Days to cover for lead time (reorder point)
COVERAGE_TARGET     = 30       # Days of stock to target (optimal level)
