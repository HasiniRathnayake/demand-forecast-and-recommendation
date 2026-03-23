# 📊 Demand Forecast Dashboard — Sunrise Supermarket

**IT2021 AIML Project | Group 2026-Y2-S2-KU-AI-02**  
**Developer:** Rathnayake R.M.H.T — Demand Forecast Dashboard & Model Training

---

## Overview

AI-powered demand forecasting dashboard for Sunrise Supermarket, Kandy, Sri Lanka.  
Predicts future demand for 6 key product categories using XGBoost & Random Forest models.

### Focused Product Categories
`Sugar` | `Rice` | `Flour` | `Dairy` | `Oil` | `Beverages`

---

## Tech Stack

| Layer        | Technology                  |
|-------------|-----------------------------|
| Frontend     | Streamlit                   |
| Backend      | Python 3.11                 |
| Database     | Supabase (PostgreSQL)       |
| Visualization| Plotly                      |
| ML (Future)  | Scikit-learn, XGBoost, RF   |
| Weather API  | OpenWeatherMap (Kandy, LK)  |

---

## Project Structure

```
demand-forecast-dashboard/
├── app.py                  ← Entry point
├── config/settings.py      ← Config & constants
├── data/                   ← Database layer
├── services/               ← Business logic
├── ml/                     ← Model interface
├── ui/                     ← UI components
└── tests/                  ← Unit & validation tests
```

---

## Setup (Local)

### Prerequisites
- Python 3.11
- Supabase account with project set up

### 1. Clone & Navigate
```bash
git clone <repo-url>
cd demand-forecast-dashboard
```

### 2. Create Virtual Environment (Python 3.11)
```bash
py -3.11 -m venv venv311
venv311\Scripts\activate   # Windows
# OR
source venv311/bin/activate # Mac/Linux
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
Create a `.env` file in the root:
```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
WEATHER_API_KEY=your_openweathermap_api_key
```

> **Weather API**: Get a free key at https://openweathermap.org/api  
> Currently uses Kandy, LK coordinates (7.2906, 80.6337)

### 5. Run the Dashboard
```bash
streamlit run app.py
```

---

## Switching from Mock → Real ML Model

The system is architected to swap models with minimal code change.

In `ml/model_interface.py`, implement the `BaseForecaster` interface in a new class.  
In `services/forecast_service.py`, swap `MockForecaster` → your trained model class.

```python
# services/forecast_service.py — change this one line:
from ml.mock_forecaster import MockForecaster as ActiveModel
# → to:
from ml.xgboost_forecaster import XGBoostForecaster as ActiveModel
```

---

## Supabase Tables Required

```sql
product_catalog (product_code, product_name, category, sub_category, 
                 unit_price, offer_price, package_size, unit_of_measure,
                 is_perishable, shelf_life_days, is_ai_supported)

daily_sales_history (product_code, transaction_date, quantity_sold, is_promotion)

demand_forecasts (product_code, forecast_date, predicted_demand, confidence_level,
                  model_version, model_accuracy, created_at)
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Git Workflow

```bash
# First time
git checkout -b feature/demand-forecast

# Regular commits
git add .
git commit -m "feat: add forecast tab with confidence intervals"
git push origin feature/demand-forecast
```

---

## Current Status (Progress 2)

- [x] Dashboard UI with forecast, historical, and data tabs
- [x] Mock ML model with XGBoost/RF interface ready
- [x] Supabase integration (read/write)
- [x] Weather API integration (Kandy)
- [x] Input validation & error handling
- [x] Unit tests
- [ ] Real XGBoost/RF model training (Progress 3)
- [ ] Live client sales data integration

---

*Progress 2 | IT2021 AIML Project | SLIIT*