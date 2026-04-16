# scripts/segmentation.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.db_connection import DatabaseConnection
from sklearn.cluster import KMeans
import pandas as pd
import numpy as np

class CustomerSegmentation:
    def __init__(self):
        self.db = DatabaseConnection()
        # Defaults are aligned with the current Supabase clustering output table.
        self.cluster_table = os.getenv("CLUSTER_RESULTS_TABLE", "customer_segment_assignment")
        self.cluster_customer_id_col = os.getenv("CLUSTER_CUSTOMER_ID_COLUMN", "customer_id")
        self.cluster_label_col = os.getenv("CLUSTER_LABEL_COLUMN", "segment")

        # Update this mapping if your clustering model uses a different label meaning.
        self.cluster_to_segment = {
            # Notebook loyalty_status labels
            "💎 vip": "VIP Customer",
            "🛒 regular": "Regular Customer",
            "🌱 new customer": "New Customer",
            "😴 churned": "Churned",
            # Notebook product-preference labels sometimes end up in source data
            "🐟 fresh & protein lovers": "Regular Customer",
            "🥦 balanced shoppers": "Regular Customer",
            "👶 family & baby care": "Regular Customer",
            "🥤 drink & health focused": "Regular Customer",
            # Direct segment IDs from notebook export mapping
            "1": "VIP Customer",
            "3": "Regular Customer",
            "6": "New Customer",
            "7": "Churned",
            "vip": "VIP Customer",
            "high value": "High Value",
            "regular": "Regular Customer",
            "regular customer": "Regular Customer",
            "at risk": "At Risk",
            "occasional": "Occasional",
            "new": "New Customer",
            "new customer": "New Customer",
            "churned": "Churned",
        }

        # Taste preference mapping from product categories
        self.category_to_taste = {
            'Fruits & Veg': '🥦 balanced shoppers',
            'Dairy': '🥦 balanced shoppers',
            'Meat': '🐟 fresh & protein lovers',
            'Seafood': '🐟 fresh & protein lovers',
            'Beverages': '🥤 drink & health focused',
            'Nutrition & Fiber': '🥤 drink & health focused',
            'Baby': '👶 family & baby care',
            'House Care': '👶 family & baby care',
            'Snacks': '🥦 balanced shoppers',
            'Desserts & Ingredients': '🥦 balanced shoppers',
            'Flour': '🥦 balanced shoppers',
            'Noodles & Soup': '🥦 balanced shoppers',
            'Oil': '🥦 balanced shoppers',
            'Rice': '🥦 balanced shoppers',
            'Spreads & Jams': '🥦 balanced shoppers',
            'Sugar': '🥦 balanced shoppers',
        }

    def _get_assignment_segment_column(self):
        cols = self.db.fetch_all(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'customer_segment_assignment'
            """
        )
        col_set = {c[0] for c in cols}
        if 'segment_id' in col_set:
            return 'segment_id'
        if 'segment' in col_set:
            return 'segment'
        return None

    def get_cluster_assignments(self):
        query = """
        SELECT
            c.customer_id,
            c.first_name,
            c.email,
            c.email_notification_enabled,
            c.promotional_emails_allowed,
            cr.{cluster_label_col} as cluster_label
        FROM customers c
        JOIN {cluster_table} cr
          ON c.{cluster_customer_id_col} = cr.{cluster_customer_id_col}
        WHERE c.is_active = TRUE
        ORDER BY c.customer_id
        """
        rows = self.db.fetch_all(query.format(
            cluster_table=self.cluster_table,
            cluster_customer_id_col=self.cluster_customer_id_col,
            cluster_label_col=self.cluster_label_col,
        ))
        if not rows:
            return []

        customers = []
        for row in rows:
            cluster_label = str(row[5]).strip() if row[5] is not None else ""
            customers.append({
                'customer_id':   row[0],
                'first_name':    row[1] or 'Customer',
                'email':         row[2],
                'email_enabled': row[3],
                'promo_allowed': row[4],
                'cluster_label': cluster_label,
            })
        return customers

    def map_cluster_to_segment(self, cluster_label):
        normalized = str(cluster_label).strip().lower()
        if normalized in self.cluster_to_segment:
            return self.cluster_to_segment[normalized]

        # If labels are numeric IDs from customer_segments.segment_id, resolve directly from DB.
        if normalized.isdigit():
            seg_row = self.db.fetch_one(
                "SELECT segment_name FROM customer_segments WHERE segment_id = %s",
                [int(normalized)]
            )
            if seg_row:
                return seg_row[0]

        return 'Occasional'

    def cluster_by_taste_preferences(self):
        """Assign taste preferences based on most purchased product category."""
        # Get customer purchase data by category
        query = """
        SELECT 
            c.customer_id,
            p.category,
            COALESCE(SUM(ti.quantity), 0) as total_qty
        FROM customers c
        JOIN transactions t ON c.customer_id = t.customer_id
        JOIN transaction_items ti ON t.transaction_id = ti.transaction_id
        JOIN product_catalog p ON ti.product_code = p.product_code
        WHERE c.is_active = TRUE
        GROUP BY c.customer_id, p.category
        ORDER BY c.customer_id, total_qty DESC
        """
        rows = self.db.fetch_all(query)
        if not rows:
            return []

        # Group by customer and find most purchased category
        customer_tastes = {}
        for row in rows:
            customer_id = row[0]
            category = row[1]
            qty = row[2]
            if customer_id not in customer_tastes:
                customer_tastes[customer_id] = (category, qty)
            elif qty > customer_tastes[customer_id][1]:
                customer_tastes[customer_id] = (category, qty)

        # Get existing customer IDs in assignment table
        existing_ids = set()
        existing_rows = self.db.fetch_all("SELECT customer_id FROM customer_segment_assignment")
        for row in existing_rows:
            existing_ids.add(row[0])

        # Assign taste based on category
        customers = []
        for customer_id, (category, qty) in customer_tastes.items():
            taste = self.category_to_taste.get(category, '🥦 balanced shoppers')
            customers.append({
                'customer_id': customer_id,
                'taste': taste,
            })
            
            if customer_id in existing_ids:
                self.db.execute_query(
                    """UPDATE customer_segment_assignment
                       SET product_preference = %s,
                           assigned_date = CURRENT_DATE
                       WHERE customer_id = %s""",
                    [taste, customer_id]
                )
            else:
                self.db.execute_query(
                    """INSERT INTO customer_segment_assignment
                       (customer_id, product_preference, assigned_date)
                       VALUES (%s, %s, CURRENT_DATE)""",
                    [customer_id, taste]
                )

        return customers

    def run(self, mode='rfm'):
        if mode == 'taste':
            return self.cluster_by_taste_preferences()
        
        # Original RFM clustering sync
        customers = self.get_cluster_assignments()
        if not customers:
            return []

        # Ensure segments exist
        segments = [
            ('VIP Customer',     6, 10000, 'Top customers with high frequency and spend'),
            ('High Value',       3, 15000, 'High spenders but less frequent'),
            ('Regular Customer', 3,  5000, 'Regular shoppers'),
            ('At Risk',          2,  5000, 'Previously good but inactive >30 days'),
            ('Occasional',       1,  1000, 'Infrequent shoppers'),
            ('New Customer',     0,     0, 'Just joined, no purchases'),
            ('Churned',          1,     0, 'Inactive for >60 days'),
        ]
        for seg in segments:
            exists = self.db.fetch_one(
                "SELECT segment_id FROM customer_segments WHERE segment_name = %s",
                [seg[0]]
            )
            if not exists:
                self.db.execute_query(
                    """INSERT INTO customer_segments
                       (segment_name, min_transaction_count, min_total_spent, description)
                       VALUES (%s, %s, %s, %s)""",
                    seg
                )

        results = []
        assignment_segment_col = self._get_assignment_segment_column()
        if not assignment_segment_col:
            print("❌ Missing segment column in customer_segment_assignment (need segment_id or segment)")
            return []

        for c in customers:
            seg_name = self.map_cluster_to_segment(c['cluster_label'])
            c['segment'] = seg_name

            seg_row = self.db.fetch_one(
                "SELECT segment_id FROM customer_segments WHERE segment_name = %s",
                [seg_name]
            )
            if seg_row:
                seg_id = seg_row[0]
                # Handle both schema variants: segment_id (legacy) and segment (current).
                if assignment_segment_col == 'segment_id':
                    self.db.execute_query(
                        "DELETE FROM customer_segment_assignment WHERE customer_id = %s",
                        [c['customer_id']]
                    )
                    self.db.execute_query(
                        """INSERT INTO customer_segment_assignment
                           (customer_id, segment_id, assigned_date)
                           VALUES (%s, %s, CURRENT_DATE)""",
                        [c['customer_id'], seg_id]
                    )
                else:
                    exists = self.db.fetch_one(
                        "SELECT 1 FROM customer_segment_assignment WHERE customer_id = %s",
                        [c['customer_id']]
                    )
                    if exists:
                        self.db.execute_query(
                            """UPDATE customer_segment_assignment
                               SET segment = %s,
                                   assigned_date = CURRENT_DATE
                               WHERE customer_id = %s""",
                            [seg_id, c['customer_id']]
                        )
                    else:
                        self.db.execute_query(
                            """INSERT INTO customer_segment_assignment
                               (customer_id, segment, assigned_date)
                               VALUES (%s, %s, CURRENT_DATE)""",
                            [c['customer_id'], seg_id]
                        )
            results.append(c)

        return results


if __name__ == "__main__":
    seg = CustomerSegmentation()
    results = seg.run()
    print(f"\n✅ Segmented {len(results)} customers")
    for c in results:
        print(f"  {c['first_name']:15} | cluster={c['cluster_label']} → {c['segment']}")