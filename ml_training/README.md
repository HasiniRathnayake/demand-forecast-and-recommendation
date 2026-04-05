# ML Training Pipeline

## Setup
```bash
pip install xgboost scikit-learn pandas numpy matplotlib
```

## Run Training
1. Copy `featured_sales_data.csv` into this folder
2. From project root run:
```bash
python ml_training/train_evaluate.py
```

## Outputs (ml_training/outputs/)
- `xgboost_v1.pkl` — trained XGBoost model
- `rf_v1.pkl` — trained Random Forest model  
- `model_metrics.json` — evaluation metrics for both models
- `feature_importance.png` — feature importance chart
- `actual_vs_predicted.png` — prediction vs actual chart
- `evaluation_report.txt` — human-readable summary

Models are also automatically copied to `ml/saved_models/` for dashboard use.

## Activate Real Model in Dashboard
In `services/forecast_service.py`, change:
```python
from ml.mock_forecaster import MockForecaster as ActiveModel
# to:
from ml.xgboost_forecaster import XGBoostForecaster as ActiveModel
# or:
from ml.rf_forecaster import RFForecaster as ActiveModel
```