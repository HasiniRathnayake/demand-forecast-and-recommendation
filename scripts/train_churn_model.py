import os
import sys
import json
from datetime import datetime
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
from sklearn.model_selection import train_test_split, cross_val_score

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.db_connection import DatabaseConnection


def load_training_data() -> pd.DataFrame:
    db = DatabaseConnection()
    rows = db.fetch_all(
        """
        SELECT
            c.customer_id,
            COALESCE(SUM(t.total_amount), 0) AS total_spent,
            COALESCE((CURRENT_DATE - MAX(DATE(t.transaction_date))), 90) AS days_inactive,
            CASE
                WHEN LOWER(cs.segment_name) IN ('churned', 'at risk') THEN 1
                ELSE 0
            END AS churn_label
        FROM customers c
        LEFT JOIN customer_segment_assignment csa ON c.customer_id = csa.customer_id
        LEFT JOIN customer_segments cs ON cs.segment_id = csa.segment_id
        LEFT JOIN transactions t ON c.customer_id = t.customer_id
        WHERE c.is_active = TRUE
        GROUP BY c.customer_id, cs.segment_name
        """
    )

    df = pd.DataFrame(rows, columns=["customer_id", "total_spent", "days_inactive", "churn_label"])
    if df.empty:
        return df

    # Collapse potential duplicate rows per customer if segment mappings overlap.
    df = (
        df.groupby("customer_id", as_index=False)
        .agg(
            total_spent=("total_spent", "max"),
            days_inactive=("days_inactive", "max"),
            churn_label=("churn_label", "max"),
        )
    )
    return df


def train_and_save_model(output_path: str) -> None:
    train_df = load_training_data()
    if train_df.empty:
        raise RuntimeError("No training rows found. Ensure customer, segment, and transaction data exist.")

    x_train = train_df[["total_spent", "days_inactive"]]
    y_train = train_df["churn_label"]

    x_fit, x_test, y_fit, y_test = train_test_split(
        x_train,
        y_train,
        test_size=0.2,
        random_state=42,
        stratify=y_train if y_train.nunique() > 1 else None,
    )

    model = RandomForestClassifier(n_estimators=200, random_state=42)
    model.fit(x_fit, y_fit)

    y_pred = model.predict(x_test)
    y_prob = model.predict_proba(x_test)[:, 1] if hasattr(model, "predict_proba") else None

    cv_scores = cross_val_score(
        model,
        x_train,
        y_train,
        cv=5 if len(train_df) >= 5 else 3,
        scoring="f1",
    )

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    roc_auc = roc_auc_score(y_test, y_prob) if y_prob is not None and y_test.nunique() > 1 else None
    confusion = confusion_matrix(y_test, y_pred).tolist()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    joblib.dump(model, output_path)

    metadata = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "training_rows": int(len(train_df)),
        "churn_ratio": float(y_train.mean()),
        "features": ["total_spent", "days_inactive"],
        "model_type": "RandomForestClassifier",
        "evaluation": {
            "holdout_accuracy": round(float(accuracy), 4),
            "holdout_precision": round(float(precision), 4),
            "holdout_recall": round(float(recall), 4),
            "holdout_f1": round(float(f1), 4),
            "holdout_roc_auc": round(float(roc_auc), 4) if roc_auc is not None else None,
            "holdout_confusion_matrix": confusion,
            "cv_f1_mean": round(float(cv_scores.mean()), 4),
            "cv_f1_std": round(float(cv_scores.std()), 4),
        },
    }
    meta_path = output_path.replace(".pkl", "_meta.json")
    with open(meta_path, "w", encoding="utf-8") as meta_file:
        json.dump(metadata, meta_file, indent=2)

    print(f"Model saved successfully: {output_path}")
    print(f"Metadata saved: {meta_path}")
    print(f"Training rows: {len(train_df)}")
    print(f"Churn ratio: {y_train.mean():.2%}")
    print(f"Holdout accuracy: {accuracy:.4f}")
    print(f"Holdout precision: {precision:.4f}")
    print(f"Holdout recall: {recall:.4f}")
    print(f"Holdout F1: {f1:.4f}")
    if roc_auc is not None:
        print(f"Holdout ROC-AUC: {roc_auc:.4f}")
    print(f"Cross-val F1: {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")


if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_out = os.path.join(root_dir, "ml", "saved_models", "churn_model.pkl")
    train_and_save_model(model_out)
