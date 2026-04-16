# scripts/apriori_engine.py
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.db_connection import DatabaseConnection
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder

class AprioriEngine:
    def __init__(self):
        self.db = DatabaseConnection()

    def load_transactions(self):
        """Load all transaction items from DB"""
        rows = self.db.fetch_all("""
            SELECT t.transaction_id, p.product_code
            FROM transaction_items ti
            JOIN transactions t ON ti.transaction_id = t.transaction_id
            JOIN product_catalog p ON ti.product_code = p.product_code
            ORDER BY t.transaction_id
        """)
        if not rows:
            print("❌ No transaction data found")
            return None

        # Group by transaction → list of products per transaction
        basket = {}
        for tx_id, product_code in rows:
            if tx_id not in basket:
                basket[tx_id] = []
            basket[tx_id].append(product_code)

        transactions = list(basket.values())
        print(f"✅ Loaded {len(transactions)} transactions")
        return transactions

    def run_apriori(self, transactions, min_support=0.02, min_confidence=0.20):
        """Run Apriori algorithm and return rules"""
        if not transactions:
            return None

        print("🔄 Running Apriori algorithm...")

        # Encode transactions
        te      = TransactionEncoder()
        te_array = te.fit(transactions).transform(transactions)
        df      = pd.DataFrame(te_array, columns=te.columns_)

        print(f"📊 Transaction matrix: {df.shape[0]} transactions × {df.shape[1]} products")

        # Find frequent itemsets
        frequent_itemsets = apriori(
            df,
            min_support=min_support,
            use_colnames=True
        )

        if frequent_itemsets.empty:
            print("⚠️ No frequent itemsets found — try lowering min_support")
            return None

        print(f"✅ Found {len(frequent_itemsets)} frequent itemsets")

        # Generate association rules (notebook-aligned confidence threshold)
        rules = association_rules(
            frequent_itemsets,
            metric="confidence",
            min_threshold=min_confidence
        )

        if rules.empty:
            print("⚠️ No rules generated — try lowering min_confidence")
            return None

        # Notebook-aligned filters
        rules = rules[(rules['lift'] >= 1.1) & (rules['support'] >= 0.01)]
        rules['antecedent_len'] = rules['antecedents'].apply(len)
        rules['consequent_len'] = rules['consequents'].apply(len)

        # Keep only single item → single item rules
        rules = rules[
            (rules['antecedent_len'] == 1) &
            (rules['consequent_len'] == 1)
        ].copy()

        if rules.empty:
            print("⚠️ Rules exist but none passed notebook filter constraints")
            return None

        # Extract product codes
        rules['antecedent_code'] = rules['antecedents'].apply(
            lambda x: list(x)[0]
        )
        rules['consequent_code'] = rules['consequents'].apply(
            lambda x: list(x)[0]
        )

        # Remove symmetric duplicates (A->B vs B->A) using canonical key
        rules['rule_key'] = rules.apply(
            lambda row: tuple(sorted([row['antecedent_code'], row['consequent_code']])),
            axis=1,
        )
        rules = rules.drop_duplicates('rule_key')

        # Notebook-aligned ranking
        rules = rules.sort_values(['lift', 'confidence', 'support'], ascending=False)

        print(f"✅ Generated {len(rules)} association rules")
        print("\nTop 5 rules:")
        for _, row in rules.head(5).iterrows():
            print(f"  {row['antecedent_code']} → {row['consequent_code']} "
                  f"(conf: {row['confidence']:.2f}, lift: {row['lift']:.2f})")

        return rules

    def save_rules_to_db(self, rules):
        """Save rules to association_rules table"""
        if rules is None or rules.empty:
            print("❌ No rules to save")
            return

        # Clear old rules
        self.db.execute_query("DELETE FROM association_rules")

        saved = 0
        for _, row in rules.iterrows():
            self.db.execute_query("""
                INSERT INTO association_rules
                (antecedent_product_code, consequent_product_code,
                 support, confidence, lift, last_updated)
                VALUES (%s, %s, %s, %s, %s, CURRENT_DATE)
            """, [
                row['antecedent_code'],
                row['consequent_code'],
                float(row['support']),
                float(row['confidence']),
                float(row['lift'])
            ])
            saved += 1

        print(f"✅ Saved {saved} rules to database")

    def get_recommendations(self, customer_id, top_n=6):
        """
        Get product recommendations for a customer
        based on their purchase history + association rules
        """
        # Get products customer has bought
        bought = self.db.fetch_all("""
            SELECT DISTINCT ti.product_code
            FROM transaction_items ti
            JOIN transactions t ON ti.transaction_id = t.transaction_id
            WHERE t.customer_id = %s
        """, [customer_id])

        if not bought:
            # No history — return popular products
            return self._get_popular_products(top_n)

        bought_codes = [r[0] for r in bought]

        # Find rules where antecedent is in bought products
        placeholders = ','.join(['%s'] * len(bought_codes))
        rules = self.db.fetch_all(f"""
            SELECT ar.consequent_product_code,
                   p.product_name, p.category,
                   p.unit_price,
                   COALESCE(p.offer_price, p.unit_price) as offer_price,
                   ar.confidence, ar.lift
            FROM association_rules ar
            JOIN product_catalog p ON ar.consequent_product_code = p.product_code
            WHERE ar.antecedent_product_code IN ({placeholders})
            AND ar.consequent_product_code NOT IN ({placeholders})
            AND p.is_ai_supported = TRUE
            ORDER BY ar.lift DESC, ar.confidence DESC
            LIMIT %s
        """, bought_codes + bought_codes + [top_n])

        if rules:
            return [{
                'product_code':  r[0],
                'product_name':  r[1],
                'category':      r[2],
                'unit_price':    float(r[3]),
                'offer_price':   float(r[4]),
                'confidence':    float(r[5]),
                'lift':          float(r[6]),
                'reason':        'Frequently bought together'
            } for r in rules]

        # Fallback to popular if no rules match
        return self._get_popular_products(top_n)

    def _get_popular_products(self, top_n=6):
        """Fallback: return most popular products"""
        rows = self.db.fetch_all("""
            SELECT p.product_code, p.product_name, p.category,
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
        """, [top_n])

        return [{
            'product_code': r[0],
            'product_name': r[1],
            'category':     r[2],
            'unit_price':   float(r[3]),
            'offer_price':  float(r[4]),
            'confidence':   0,
            'lift':         0,
            'reason':       'Popular product'
        } for r in rows]

    def run(self):
        """Full pipeline: load → apriori → save"""
        print("🚀 Starting Apriori Engine")
        print("=" * 50)

        transactions = self.load_transactions()
        if not transactions:
            return False

        # Try with low support since we have small dataset
        rules = self.run_apriori(
            transactions,
            min_support=0.02,
            min_confidence=0.20
        )

        if rules is not None:
            self.save_rules_to_db(rules)
            return True
        else:
            print("⚠️ No rules found with current thresholds")
            print("💡 This is normal with small datasets")
            print("   Recommendations will use popular products as fallback")
            return False


if __name__ == "__main__":
    engine = AprioriEngine()
    engine.run()