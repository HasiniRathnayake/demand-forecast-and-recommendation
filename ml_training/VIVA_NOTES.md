# Viva Notes: Loyalty AI Component

## 1) Churn Prediction
Use `scripts/train_churn_model.py`.

What it now does:
- Trains a `RandomForestClassifier`
- Splits data into train/test
- Reports holdout metrics:
  - accuracy
  - precision
  - recall
  - F1
  - ROC-AUC
  - confusion matrix
- Saves metrics into `ml/saved_models/churn_model_meta.json`

What to say in viva:
- Accuracy alone is not enough for churn because churn data is usually imbalanced.
- Precision matters when you want fewer false alarms.
- Recall matters when you want to catch most churners.
- F1 gives a balanced summary.
- ROC-AUC shows how well the model separates churn vs non-churn.

## 2) Loyalty Clustering
Use the segmentation pipeline and the notebook.

What to say in viva:
- RFM clustering groups customers by recency, frequency, and monetary value.
- Taste preference clustering groups customers by purchase category patterns.
- For KMeans, try multiple values of `k`.
- Compare elbow method and silhouette score.
- Pick the `k` where inertia slows down and silhouette is highest or near-highest.

## 3) Apriori Recommendations
Use the Apriori script / notebook.

What to say in viva:
- Evaluate by support, confidence, and lift.
- Higher lift means stronger-than-random product association.
- No `k` value is used in Apriori.

## 4) Suggested Split for 3 People
### Person 1
- Problem statement
- Data sources
- Why AI was needed
- High-level loyalty architecture

### Person 2
- Churn model
- Metrics and how evaluation was done
- Why accuracy alone is not enough
- What the saved model is used for in the app

### Person 3
- RFM and taste clustering
- How `k` was chosen
- Apriori recommendations
- How the outputs are used in the dashboard and campaigns

## 5) Short Answer Lines for Viva
- "We used a train/test split and cross-validation to check generalization."
- "For churn, recall and F1 are more important than accuracy alone."
- "For clustering, we selected `k` using elbow and silhouette score."
- "For Apriori, we judged rules by support, confidence, and lift."
- "The loyalty AI component is split into prediction, clustering, and recommendation modules."
