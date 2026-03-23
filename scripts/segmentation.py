# scripts/segmentation.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.db_connection import DatabaseConnection

class CustomerSegmentation:
    def __init__(self):
        self.db = DatabaseConnection()

    def get_customer_metrics(self):
        query = """
        SELECT 
            c.customer_id,
            c.first_name,
            c.email,
            c.email_notification_enabled,
            c.promotional_emails_allowed,
            COUNT(DISTINCT t.transaction_id) as transaction_count,
            COALESCE(SUM(t.total_amount), 0) as total_spent,
            COALESCE(AVG(t.total_amount), 0) as avg_basket,
            MAX(t.transaction_date) as last_purchase,
            COALESCE(CURRENT_DATE - MAX(t.transaction_date), 999) as days_inactive
        FROM customers c
        LEFT JOIN transactions t ON c.customer_id = t.customer_id
        WHERE c.is_active = TRUE
        GROUP BY c.customer_id, c.first_name, c.email,
                 c.email_notification_enabled, c.promotional_emails_allowed
        ORDER BY total_spent DESC
        """
        rows = self.db.fetch_all(query)
        customers = []
        for row in rows:
            customers.append({
                'customer_id':   row[0],
                'first_name':    row[1] or 'Customer',
                'email':         row[2],
                'email_enabled': row[3],
                'promo_allowed': row[4],
                'tx_count':      int(row[5]),
                'total_spent':   float(row[6]),
                'avg_basket':    float(row[7]),
                'last_purchase': row[8],
                'days_inactive': int(row[9]) if row[9] else 999
            })
        return customers

    def assign_segment(self, c):
        if c['tx_count'] == 0:
            return 'New Customer'
        if c['total_spent'] >= 10000 and c['tx_count'] >= 6:
            return 'VIP Customer'
        if c['total_spent'] >= 15000:
            return 'High Value'
        if c['total_spent'] >= 5000 and c['days_inactive'] <= 30:
            return 'Regular Customer'
        if c['total_spent'] >= 5000 and c['days_inactive'] > 30:
            return 'At Risk'
        if c['days_inactive'] > 60:
            return 'Churned'
        return 'Occasional'

    def run(self):
        customers = self.get_customer_metrics()
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
        for c in customers:
            seg_name = self.assign_segment(c)
            c['segment'] = seg_name

            seg_row = self.db.fetch_one(
                "SELECT segment_id FROM customer_segments WHERE segment_name = %s",
                [seg_name]
            )
            if seg_row:
                seg_id = seg_row[0]
                # Remove old assignment then insert fresh
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
            results.append(c)

        return results


if __name__ == "__main__":
    seg = CustomerSegmentation()
    results = seg.run()
    print(f"\n✅ Segmented {len(results)} customers")
    for c in results:
        print(f"  {c['first_name']:15} → {c['segment']}")