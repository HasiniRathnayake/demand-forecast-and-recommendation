# ☀️ Sunrise Super — AI Inventory System

A unified, AI-powered platform for intelligent retail inventory management built for the **2026-Y2-S2-KU-AI-02** project. 

The system provides predictive, automated, and streamlined tools across six different business domains, backed by a predictive Machine Learning pipeline and a centralized Supabase database.

---

## 🚀 Key Modules & Dashboards

The system consists of a shared home landing page linking to 6 specialized dashboards:

### 1. Procurement & Stock Replenishment (Core ML Module)
*Owned by: IT24100168*
- Core functionality of the platform utilizing a **Python Machine Learning Pipeline**.
- Aggregates historical sales, current stock, and pending POs.
- Features dynamic reorder point prediction using **XGBoost** and **Prophet** time-series forecasting.
- Generates intelligent "Suggested Qty" insights with automated urgency classification.
- Dashboard allows procurement officers to 1-click Approve or Reject ML-generated orders.

### 2. Demand Forecasting
- Predictive visualization of weekly sales.
- Integrates historical sales volume with a custom holiday calendar (e.g., Ramadan, Eid) to warn of sudden demand spikes.

### 3. Waste & Performance Monitor
- Dedicated log for perishable stock wastage.
- Visualizes waste trends over time and compares AI predictions against actual historical performance to calculate financial ROI.

### 4. Short-Shipment Detector
- Acts as a financial security guard for received goods.
- Flags discrepancies where `Invoiced Qty > Received Qty`.
- Maintains a real-time risk profile for incoming shipments.

### 5. Smart Loyalty & Promotion Manager
- Groups customers dynamically into segments (e.g., High Value, At Risk).
- Allows marketing teams to manage and track the success of targeted digital promotions out to specific demographic sets.

### 6. Smart Inventory Intake
- A mobile-responsive digital intake form for staff on the warehouse floor.
- Real-time ±10% mathematical anomaly detection alerts staff immediately if physical goods do not match the expected shipment tally.

---

## 🛠️ Technology Stack

* **Frontend:** Pure HTML5, CSS3, Vanilla JavaScript (ES6+). No heavy frameworks, allowing for lightning-fast load times.
* **Design System:** Custom CSS variables (`shared.css`) implementing a premium, glassmorphism "Luxury Dark Mode" with full Light Mode toggle support.
* **Backend / Database:** [Supabase](https://supabase.com) (PostgreSQL) integrated via REST APIs and Row-Level Security.
* **Local Server:** Lightweight Node.js server (`server.js`) for routing and MIME type handling.
* **Data Visualization:** Chart.js for all KPI graphs, line charts, and bar charts.
* **Machine Learning Pipeline (`/ml`):** Python 3.10+, Pandas, Scikit-Learn (K-Means Clustering, Random Forests), XGBoost, and Meta Prophet.

---

## ⚙️ Setup & Installation

### 1. Database Setup
A single SQL script provisions the entire database structure.
1. Log into your Supabase project.
2. Open the SQL Editor.
3. Copy the contents of `setup_tables.sql` and run it to construct all 7 data tables and configure constraints.

### 2. Running the Dashboards (Frontend)
Ensure you have Node.js installed.
```bash
# Start the local development server
node server.js
```
The application will be accessible at: **http://localhost:3456**

### 3. Running the ML Pipeline (Backend Python)
The Python pipeline connects to Supabase, generates predictions, and writes fresh replenishment orders back to the database.
```bash
cd ml
pip install -r requirements.txt

# Run the full pipeline (train models, predict, and upload)
python pipeline.py

# Run a dry-run (view predictions in terminal without uploading)
python pipeline.py --dry-run
```

---

## 🎨 Theme Support
The UI features a fully integrated **Dark / Light mode** persistent across page navigations via `localStorage`. The theme logic is handled entirely by CSS cascading attribute selectors (`data-theme="light"`), ensuring zero-flicker loading.