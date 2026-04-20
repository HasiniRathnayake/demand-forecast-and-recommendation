# scripts/segmentation.py
#
# Syncs customer segment assignments to the database.
# Notebook (customer_clusters.csv) handles historic customers.
# This script handles new customers who joined after the last model run.

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

from scripts.db_connection import DatabaseConnection


# ── Segment reference data (matches your DB exactly) ─────────
SEGMENTS = [
    ("VIP Customer",     6, 10000, "Top customers with high frequency and spend"),
    ("High Value",       3, 15000, "High spenders but less frequent"),
    ("Regular Customer", 3,  5000, "Regular shoppers"),
    ("At Risk",          2,  5000, "Previously good but inactive >30 days"),
    ("Occasional",       1,  1000, "Infrequent shoppers"),
    ("New Customer",     0,     0, "Just joined, no purchases"),
    ("Churned",          1,     0, "Inactive for >60 days"),
]

# Matches notebook loyalty labels exactly
SEG_ID_MAP = {
    'VIP':        1,
    'Regular':    3,
    'Occasional': 5,
    'Churned':    7,
    'New Customer': 6,  # only used for fallback (new customers not in notebook)
}


class CustomerSegmentation:

    def __init__(self):
        self.db = DatabaseConnection()

    # =========================================================================
    # DATABASE HELPERS
    # =========================================================================

    def _ensure_segments_exist(self):
        """Insert any missing rows into customer_segments."""
        for name, min_tx, min_spent, desc in SEGMENTS:
            exists = self.db.fetch_one(
                "SELECT 1 FROM customer_segments WHERE segment_name = %s", [name]
            )
            if not exists:
                self.db.execute_query(
                    """INSERT INTO customer_segments
                           (segment_name, min_transaction_count, min_total_spent, description)
                       VALUES (%s, %s, %s, %s)""",
                    [name, min_tx, min_spent, desc],
                )

    def _upsert_assignment(self, customer_id, segment_id, product_preference):
        """Insert or update one row in customer_segment_assignment."""
        exists = self.db.fetch_one(
            "SELECT 1 FROM customer_segment_assignment WHERE customer_id = %s",
            [customer_id],
        )
        if exists:
            self.db.execute_query(
                """UPDATE customer_segment_assignment
                      SET segment_id         = %s,
                          product_preference = %s,
                          assigned_date      = CURRENT_DATE
                    WHERE customer_id = %s""",
                [segment_id, product_preference, customer_id],
            )
        else:
            self.db.execute_query(
                """INSERT INTO customer_segment_assignment
                       (customer_id, segment_id, product_preference, assigned_date)
                   VALUES (%s, %s, %s, CURRENT_DATE)""",
                [customer_id, segment_id, product_preference],
            )

    # =========================================================================
    # FEATURE BUILDER
    # =========================================================================

    def _fetch_customers(self) -> pd.DataFrame:
        """
        Returns all active customers with RFM metrics and
        existing segment assignment from DB (if any).
        """
        rows = self.db.fetch_all(
            """
            SELECT
                c.customer_id,
                c.first_name,
                c.email,
                c.email_notification_enabled,
                c.promotional_emails_allowed,
                COALESCE(COUNT(DISTINCT t.transaction_id), 0)               AS tx_count,
                COALESCE(SUM(t.total_amount), 0)                            AS total_spent,
                COALESCE(AVG(t.total_amount), 0)                            AS avg_basket,
                COALESCE(CURRENT_DATE - MAX(t.transaction_date)::date, 999) AS days_since_last,
                csa.segment_id,
                csa.product_preference
            FROM customers c
            LEFT JOIN transactions t
                   ON c.customer_id = t.customer_id
            LEFT JOIN customer_segment_assignment csa
                   ON c.customer_id = csa.customer_id
            WHERE c.is_active = TRUE
            GROUP BY
                c.customer_id, c.first_name, c.email,
                c.email_notification_enabled, c.promotional_emails_allowed,
                csa.segment_id, csa.product_preference
            ORDER BY c.customer_id
            """
        )
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            "customer_id", "first_name", "email",
            "email_enabled", "promo_allowed",
            "tx_count", "total_spent", "avg_basket", "days_since_last",
            "segment_id", "product_preference",
        ])
        return df.astype({
            "tx_count":        int,
            "total_spent":     float,
            "avg_basket":      float,
            "days_since_last": int,
        })

    # =========================================================================
    # LOYALTY CLUSTERING — mirrors notebook exactly
    # =========================================================================

    @staticmethod
    def _run_loyalty_clustering(df: pd.DataFrame) -> pd.DataFrame:
        """
        K-Means on RFM features with centroid-based labelling.
        Exactly mirrors the notebook loyalty clustering logic.
        Only runs on customers who have transactions (tx_count > 0).
        New customers (tx_count == 0) are labelled separately.
        """
        rfm_cols = ['total_spent', 'transaction_count', 'days_since_last']

        # Split: scored customers vs brand new
        has_txn = df['tx_count'] > 0
        new_customers = df[~has_txn].copy()
        existing = df[has_txn].copy()

        if existing.empty:
            df['loyalty_status'] = 'New Customer'
            return df

        # Rename to match notebook column names
        existing = existing.rename(columns={'tx_count': 'transaction_count'})

        scaler    = StandardScaler()
        rfm_scaled = scaler.fit_transform(existing[rfm_cols].values)

        km = KMeans(n_clusters=4, init='k-means++', n_init=10, random_state=42)
        existing['loyalty_cluster'] = km.fit_predict(rfm_scaled)

        rfm_means     = existing.groupby('loyalty_cluster')[rfm_cols].mean()
        spent_ranking = rfm_means['total_spent'].rank(ascending=False)
        days_ranking  = rfm_means['days_since_last'].rank(ascending=False)

        def loyalty_label(cl):
            if spent_ranking[cl] == 1:  return 'VIP'
            if days_ranking[cl] == 1:   return 'Churned'
            if spent_ranking[cl] == 2:  return 'Regular'
            return 'Occasional'

        existing['loyalty_status'] = existing['loyalty_cluster'].apply(loyalty_label)

        # Rename back
        existing = existing.rename(columns={'transaction_count': 'tx_count'})

        # New customers always get New Customer
        new_customers['loyalty_status'] = 'New Customer'

        result = pd.concat([existing, new_customers], ignore_index=True)
        return result

    # =========================================================================
    # TASTE CLUSTERING — K-Means on category spend %
    # =========================================================================

    def _fetch_category_features(self) -> pd.DataFrame:
        """Returns category-spend % per customer."""
        rows = self.db.fetch_all(
            """
            SELECT
                c.customer_id,
                p.category,
                COALESCE(SUM(ti.quantity * ti.unit_price), 0) AS category_spend
            FROM customers c
            LEFT JOIN transactions t       ON c.customer_id   = t.customer_id
            LEFT JOIN transaction_items ti ON t.transaction_id = ti.transaction_id
            LEFT JOIN product_catalog p    ON ti.product_code  = p.product_code
            WHERE c.is_active = TRUE
              AND p.category IS NOT NULL
            GROUP BY c.customer_id, p.category
            """
        )
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["customer_id", "category", "spend"])
        pivot = df.pivot_table(
            index="customer_id", columns="category",
            values="spend", fill_value=0,
        )
        pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
        pct.columns = [
            f"pct_{c.lower().replace(' ', '_').replace('&', 'and')}"
            for c in pct.columns
        ]
        return pct.reset_index()

    @staticmethod
    def _best_k(X_scaled: np.ndarray, k_range=range(2, 9)) -> int:
        """Return k with highest Silhouette Score."""
        best_k, best_score = 2, -1.0
        for k in k_range:
            km    = KMeans(n_clusters=k, init="k-means++", n_init=10, random_state=42)
            lbls  = km.fit_predict(X_scaled)
            score = silhouette_score(X_scaled, lbls)
            if score > best_score:
                best_score, best_k = score, k
        return best_k

    @staticmethod
    def _taste_label(cluster_id: int,
                     cat_features: pd.DataFrame,
                     cluster_labels: np.ndarray) -> str:
        """Maps taste cluster to preference label by dominant category."""
        mask    = cluster_labels == cluster_id
        top_col = cat_features[mask].mean().idxmax().replace("pct_", "")

        if any(k in top_col for k in {"meat", "seafood", "fish", "fresh", "protein"}):
            return "Fresh & Protein Lovers"
        if any(k in top_col for k in {"baby", "personal", "care"}):
            return "Family & Baby Care"
        if any(k in top_col for k in {"bever", "drink", "health"}):
            return "Drink & Health Focused"
        return "Balanced Shoppers"

    def _run_taste_clustering(self, customer_ids: list) -> dict:
        """
        Runs K-Means taste clustering.
        Returns {customer_id: product_preference}.
        """
        print("\n[3] Fetching category-spend features ...")
        cat_df = self._fetch_category_features()

        if cat_df.empty:
            print("    WARNING: No category data — defaulting to 'Balanced Shoppers'.")
            return {cid: "Balanced Shoppers" for cid in customer_ids}

        cat_feature_cols = [c for c in cat_df.columns if c != "customer_id"]
        X_cat = StandardScaler().fit_transform(cat_df[cat_feature_cols].values)

        print("[4] Selecting best k by Silhouette Score (range 2-8) ...")
        best_k = self._best_k(X_cat)
        print(f"    Best k = {best_k}")

        km_taste = KMeans(n_clusters=best_k, init="k-means++", n_init=10, random_state=42)
        cat_df["taste_cluster"] = km_taste.fit_predict(X_cat)

        sil = silhouette_score(X_cat, cat_df["taste_cluster"])
        print(f"    Silhouette Score (taste): {sil:.4f}")

        cat_features   = cat_df[cat_feature_cols]
        cluster_labels = cat_df["taste_cluster"].values
        cat_df["product_preference"] = cat_df["taste_cluster"].apply(
            lambda cl: self._taste_label(cl, cat_features, cluster_labels)
        )

        print("\n    Taste cluster summary:")
        for cl in sorted(cat_df["taste_cluster"].unique()):
            mask  = cat_df["taste_cluster"] == cl
            label = cat_df.loc[mask, "product_preference"].iloc[0]
            top   = cat_features[mask.values].mean().nlargest(2)
            top_s = ", ".join(
                f"{c.replace('pct_', '')}: {v:.1f}%"
                for c, v in top.items()
            )
            print(f"    Cluster {cl} ({mask.sum()} customers) -> {label}  [{top_s}]")

        return dict(zip(cat_df["customer_id"], cat_df["product_preference"]))

    # =========================================================================
    # MAIN PIPELINE
    # =========================================================================

    def run(self, mode: str | None = None) -> list:
        """
        Syncs all active customers to customer_segment_assignment.
        - Uses K-Means loyalty clustering (mirrors notebook exactly)
        - New customers (tx_count == 0) always get New Customer (segment 6)
        - Taste clustering runs for product_preference
        - ``mode`` is accepted for backward compatibility with older callers
        """
        if mode not in (None, "rfm", "taste"):
            raise ValueError("mode must be one of: None, 'rfm', 'taste'")

        if mode in ("rfm", "taste"):
            print(
                f"Note: segmentation mode '{mode}' is accepted for compatibility; "
                "the current pipeline syncs both loyalty and taste assignments."
            )

        print("=" * 60)
        print("SUNRISE SUPERMARKET — SEGMENTATION SYNC")
        print("=" * 60)

        self._ensure_segments_exist()

        # ── Fetch all customers ───────────────────────────────────────
        print("\n[1] Fetching customers from database ...")
        df = self._fetch_customers()
        if df.empty:
            print("    ERROR: No customer data found. Aborting.")
            return []
        print(f"    {len(df)} active customers loaded.")

        # ── Loyalty clustering ────────────────────────────────────────
        print("\n[2] Running loyalty clustering ...")
        df = self._run_loyalty_clustering(df)

        df["segment_id_new"] = df["loyalty_status"].map(SEG_ID_MAP)

        print("\n    Loyalty distribution:")
        for seg, n in df["loyalty_status"].value_counts().items():
            print(f"      {seg}: {n} customers")

        # ── Taste clustering ──────────────────────────────────────────
        taste_map = self._run_taste_clustering(df["customer_id"].tolist())
        df["product_preference_new"] = df["customer_id"].map(taste_map).fillna("Balanced Shoppers")

        # ── Persist to database ───────────────────────────────────────
        print("\n[5] Writing results to customer_segment_assignment ...")
        results = []
        skipped = 0

        for _, row in df.iterrows():
            seg_id = row["segment_id_new"]
            pref   = row["product_preference_new"]

            if pd.isna(seg_id):
                print(f"    WARNING: No segment_id for customer {row['customer_id']} — skipping.")
                skipped += 1
                continue

            self._upsert_assignment(row["customer_id"], int(seg_id), pref)

            results.append({
                "customer_id":        row["customer_id"],
                "first_name":         row["first_name"],
                "email":              row["email"],
                "email_enabled":      row["email_enabled"],
                "promo_allowed":      row["promo_allowed"],
                "loyalty_status":     row["loyalty_status"],
                "segment_id":         int(seg_id),
                "product_preference": pref,
                "tx_count":           row["tx_count"],
                "total_spent":        row["total_spent"],
            })

        if skipped:
            print(f"    {skipped} customers skipped.")

        print(f"\n{'='*60}")
        print(f"COMPLETE — {len(results)} customers synced.")
        print(f"{'='*60}")
        return results

    def cluster_by_taste_preferences(self) -> list:
        """Backward-compatible alias used by older test and UI code."""
        return self.run(mode="taste")


# ── CLI entry point ───────────────────────────────────────────
if __name__ == "__main__":
    seg     = CustomerSegmentation()
    results = seg.run()

    print(f"\nSample output ({min(10, len(results))} rows):")
    for c in results[:10]:
        print(
            f"  {c['first_name']:15} | "
            f"segment={c['loyalty_status']:12} (id={c['segment_id']}) | "
            f"taste={c['product_preference']}"
        )