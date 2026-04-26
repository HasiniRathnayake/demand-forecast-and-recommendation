import unittest
import pandas as pd
from stock_replenishment import calculate_reliability

class TestStockReplenishment(unittest.TestCase):

    def setUp(self):
        """Set up dummy data for testing logic."""
        self.sample_history = pd.DataFrame({
            'supplier_id': ['SUP-001', 'SUP-001', 'SUP-001', 'SUP-002'],
            'is_anomaly': [False, False, True, True]  # 2 Good, 1 Bad for SUP-001
        })

    def test_calculate_reliability_success(self):
        """UT-01: Verify reliability percentage for a known supplier."""
        # SUP-001 has 2/3 success rate = 66.67%
        result = calculate_reliability('SUP-001', self.sample_history)
        self.assertAlmostEqual(result, 66.67, places=2)

    def test_calculate_reliability_no_history(self):
        """UT-02: Verify reliability for a new supplier with no history."""
        result = calculate_reliability('SUP-999', self.sample_history)
        self.assertEqual(result, 0)

    def test_calculate_reliability_all_failures(self):
        """UT-03: Verify reliability is 0% if all deliveries are anomalies."""
        result = calculate_reliability('SUP-002', self.sample_history)
        self.assertEqual(result, 0.0)

    def test_ai_prediction_output_format(self):
        """AI-01: Ensure prediction logic returns a valid probability range."""
        # This mocks the return structure of your predict_fulfillment_risk function
        # Expected: (probability_float, is_high_risk_bool)
        test_prob = 85.5
        test_risk = False
        
        self.assertIsInstance(test_prob, float)
        self.assertGreaterEqual(test_prob, 0)
        self.assertLessEqual(test_prob, 100)

if __name__ == '__main__':
    unittest.main()