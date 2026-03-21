# scripts/offers_engine.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.db_connection import DatabaseConnection

class OffersEngine:
    def __init__(self):
        self.db = DatabaseConnection()

    def get_top_products(self, limit=5):
        """Get best selling products from product_catalog"""
        query = """
        SELECT 
            p.product_code,
            p.product_name,
            p.category,
            p.unit_price,
            COALESCE(p.offer_price, p.unit_price) as offer_price,
            COALESCE(SUM(ti.quantity), 0) as total_sold
        FROM product_catalog p
        LEFT JOIN transaction_items ti ON p.product_code = ti.product_code
        WHERE p.is_ai_supported = TRUE
        GROUP BY p.product_code, p.product_name, p.category,
                 p.unit_price, p.offer_price
        ORDER BY total_sold DESC
        LIMIT %s
        """
        rows = self.db.fetch_all(query, [limit])
        products = []
        for row in rows:
            products.append({
                'product_code': row[0],
                'product_name': row[1],
                'category':     row[2],
                'unit_price':   float(row[3]),
                'offer_price':  float(row[4]),
                'total_sold':   float(row[5])
            })
        return products

    def get_customer_favourite_categories(self, customer_id):
        """Find what categories a customer buys most"""
        query = """
        SELECT 
            p.category,
            COUNT(*) as purchase_count
        FROM transaction_items ti
        JOIN transactions t ON ti.transaction_id = t.transaction_id
        JOIN product_catalog p ON ti.product_code = p.product_code
        WHERE t.customer_id = %s
        GROUP BY p.category
        ORDER BY purchase_count DESC
        LIMIT 3
        """
        rows = self.db.fetch_all(query, [customer_id])
        return [row[0] for row in rows]

    def generate_offer_for_customer(self, customer):
        """Generate a personalized offer based on segment"""
        segment    = customer['segment']
        customer_id = customer['customer_id']
        name       = customer['first_name']

        # Get their favourite categories
        fav_categories = self.get_customer_favourite_categories(customer_id)

        # Get recommended products from their fav category if possible
        if fav_categories:
            query = """
            SELECT product_code, product_name, category,
                   unit_price,
                   COALESCE(offer_price, unit_price) as offer_price
            FROM product_catalog
            WHERE category = %s AND is_ai_supported = TRUE
            ORDER BY unit_price DESC
            LIMIT 3
            """
            rows = self.db.fetch_all(query, [fav_categories[0]])
        else:
            rows = []

        # Fall back to top products if no purchase history
        if not rows:
            top = self.get_top_products(3)
            rows = [(p['product_code'], p['product_name'], p['category'],
                     p['unit_price'], p['offer_price']) for p in top]

        recommended = []
        for row in rows:
            unit  = float(row[3])
            offer = float(row[4])
            recommended.append({
                'product_code': row[0],
                'product_name': row[1],
                'category':     row[2],
                'unit_price':   unit,
                'offer_price':  offer,
                'saving':       round(unit - offer, 2)
            })

        # Discount % based on segment
        segment_discounts = {
            'VIP Customer':     ('20% OFF just for you!',      20),
            'High Value':       ('15% OFF on your favourites', 15),
            'Regular Customer': ('10% OFF this week!',         10),
            'At Risk':          ('Come back! 25% OFF',         25),
            'Occasional':       ('Special 15% OFF for you',    15),
            'New Customer':     ('Welcome! 10% OFF',           10),
            'Churned':          ('We miss you! 30% OFF',       30),
        }
        offer_text, discount_pct = segment_discounts.get(
            segment, ('Special offer for you!', 10)
        )

        return {
            'customer_id':    customer_id,
            'customer_name':  name,
            'email':          customer['email'],
            'segment':        segment,
            'offer_text':     offer_text,
            'discount_pct':   discount_pct,
            'recommended':    recommended,
            'fav_categories': fav_categories,
            'email_enabled':  customer.get('email_enabled', False),
            'promo_allowed':  customer.get('promo_allowed', False),
        }

    def generate_all_offers(self, segmented_customers):
        """Generate offers for all customers"""
        offers = []
        for customer in segmented_customers:
            offer = self.generate_offer_for_customer(customer)
            offers.append(offer)
        return offers


if __name__ == "__main__":
    from scripts.segmentation import CustomerSegmentation
    seg    = CustomerSegmentation()
    customers = seg.run()

    engine = OffersEngine()
    offers = engine.generate_all_offers(customers)

    print(f"\n✅ Generated {len(offers)} personalized offers\n")
    for o in offers:
        print(f"  {o['customer_name']:15} | {o['segment']:20} | {o['offer_text']}")
        if o['recommended']:
            p = o['recommended'][0]
            print(f"    → Recommend: {p['product_name']} | "
                  f"Was Rs.{p['unit_price']:.2f} → Now Rs.{p['offer_price']:.2f} "
                  f"(Save Rs.{p['saving']:.2f})")