import pandas as pd
import numpy as np

class ShortShipmentDetector:
    """Main class for detecting shipment discrepancies and fraud"""
    
    @staticmethod
    def calculate_discrepancy(ordered_qty, received_qty):
        """
        Calculate discrepancy between ordered and received quantities
        With validation for edge cases
        """
        # Input validation
        if ordered_qty < 0 or received_qty < 0:
            raise ValueError("Quantities cannot be negative")
        
        discrepancy_qty = received_qty - ordered_qty
        
        # Handle division by zero
        if ordered_qty > 0:
            discrepancy_pct = (discrepancy_qty / ordered_qty) * 100
        else:
            discrepancy_pct = 0
            if received_qty > 0:
                return received_qty, 100, "📦 Unexpected Delivery"
        
        # Determine status with validation
        if abs(discrepancy_qty) < 0.01:
            status = " Accurate"
        elif discrepancy_qty < 0:
            # Validate short shipment percentage
            if discrepancy_pct < -50:
                status = " Severe Short Shipment"
            else:
                status = " Short Shipped"
        else:
            # Validate over delivery percentage
            if discrepancy_pct > 50:
                status = " Severe Over Delivery"
            else:
                status = " Over Delivered"
            
        return discrepancy_qty, round(discrepancy_pct, 1), status
    
    
    @staticmethod
    def calculate_financial_impact(discrepancy_qty, cost_price):
        """Calculate financial impact with validation"""
        if cost_price < 0:
            raise ValueError("Cost price cannot be negative")
        return discrepancy_qty * cost_price
    
    
    @staticmethod
    def detect_fraud_patterns(df, supplier_id=None):
        """
        Detect potential fraud patterns in shipment history
        Returns flagged deliveries and risk score
        """
        # Input validation
        if df.empty:
            return [" No data to analyze"], 0
        
        flags = []
        risk_score = 0
        
        # Flag 1: Consistent short shipments (>5% short for 3+ deliveries)
        df['short_pct'] = np.where(
            df['ordered_quantity'] > 0,
            (df['ordered_quantity'] - df['received_quantity']) / df['ordered_quantity'] * 100,
            0
        )
        recent = df.tail(5)
        if len(recent) >= 3 and (recent['short_pct'] > 5).sum() >= 3:
            flags.append("⚠️ PATTERN: Consistent short shipments detected")
            risk_score += 30
        
        # Flag 2: Large single discrepancy (>20%)
        large_disc = df[abs(df['discrepancy_percentage']) > 20]
        if not large_disc.empty:
            count = len(large_disc)
            flags.append(f" ALERT: {count} large discrepancies >20%")
            risk_score += min(count * 10, 40)
        
        # Flag 3: Round number fraud (discrepancies ending in 0)
        round_fraud = df[
            (abs(df['discrepancy_quantity']) > 0) & 
            (df['discrepancy_quantity'] % 10 == 0)
        ]
        if not round_fraud.empty:
            count = len(round_fraud)
            flags.append(f"💰 SUSPICIOUS: {count} round-number discrepancies")
            risk_score += min(count * 5, 20)
        
        # Flag 4: Alternating pattern (short then over then short)
        if len(df) >= 3:
            pattern = df['status'].iloc[-3:].tolist()
            if (pattern.count(' Short Shipped') >= 2 and 
                pattern.count('Over Delivered') >= 1):
                flags.append(" PATTERN: Alternating short/over shipments")
                risk_score += 25
        
        # Flag 5: Unusual frequency
        if len(df) > 10:
            avg_days_between = 30 / len(df)  # Assuming 30 day window
            if avg_days_between < 2:
                flags.append("⚡ UNUSUAL: Very high shipment frequency")
                risk_score += 15
        
        # Cap risk score at 100
        risk_score = min(risk_score, 100)
        
        # Determine risk level
        if risk_score >= 70:
            risk_level = " CRITICAL RISK"
        elif risk_score >= 40:
            risk_level = " HIGH RISK"
        elif risk_score >= 20:
            risk_level = " MEDIUM RISK"
        else:
            risk_level = " LOW RISK"
        
        return flags, risk_score, risk_level
    
    
    @staticmethod
    def validate_shipment_consistency(df):
        """
        Check for data consistency issues
        Returns list of data quality warnings
        """
        warnings = []
        
        if df.empty:
            return warnings
        
        # Check for negative quantities
        neg_ordered = df[df['ordered_quantity'] < 0]
        if not neg_ordered.empty:
            warnings.append(f"⚠️ Found {len(neg_ordered)} records with negative ordered quantities")
        
        neg_received = df[df['received_quantity'] < 0]
        if not neg_received.empty:
            warnings.append(f"⚠️ Found {len(neg_received)} records with negative received quantities")
        
        # Check for future dates
        import datetime
        today = datetime.datetime.now().date()
        future_dates = df[pd.to_datetime(df['delivery_date']).dt.date > today]
        if not future_dates.empty:
            warnings.append(f"⚠️ Found {len(future_dates)} records with future delivery dates")
        
        # Check for missing values
        missing = df[df['ordered_quantity'].isna() | df['received_quantity'].isna()]
        if not missing.empty:
            warnings.append(f"⚠️ Found {len(missing)} records with missing quantities")
        
        return warnings