import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import sys
import os

# Ensure the project root is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pages.stock_replenishment_helpers import (
    fetch_orders,
    fetch_products,
    update_order_status,
    save_supplier,
    send_po_email,
    get_next_supplier_id
)

from pages.supplier_dashboard import (
    _fetch_active_pos,
    _update_stock_in_catalog
)

class TestStockReplenishmentHelpers(unittest.TestCase):

    @patch('pages.stock_replenishment_helpers.requests.get')
    def test_fetch_orders_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'forecast_id': '123'}]
        mock_get.return_value = mock_response

        orders = fetch_orders()
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['forecast_id'], '123')

    @patch('pages.stock_replenishment_helpers.requests.get')
    def test_fetch_products_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'product_code': 'P001', 'product_name': 'Apple'}]
        mock_get.return_value = mock_response

        products = fetch_products()
        self.assertIn('P001', products)
        self.assertEqual(products['P001'], 'Apple')

    @patch('pages.stock_replenishment_helpers.requests.patch')
    @patch('pages.stock_replenishment_helpers.requests.post')
    @patch('pages.stock_replenishment_helpers.purchase_order_exists')
    @patch('pages.stock_replenishment_helpers.ensure_replenishment_row')
    @patch('pages.stock_replenishment_helpers.st')
    def test_update_order_status_approved(self, mock_st, mock_ensure, mock_po_exists, mock_post, mock_patch):
        mock_ensure.return_value = True
        mock_po_exists.return_value = False
        
        mock_patch_response = MagicMock()
        mock_patch_response.status_code = 200
        mock_patch.return_value = mock_patch_response
        
        mock_post_response = MagicMock()
        mock_post_response.status_code = 201
        mock_post.return_value = mock_post_response

        result = update_order_status('ORD-123', 'APPROVED', supplier_id='SUP-123', order_context={'order_id': 'ORD-123'}, predicted_qty=10)
        self.assertTrue(result)
        mock_ensure.assert_called_once()
        mock_patch.assert_called_once()
        mock_post.assert_called_once()

    @patch('pages.stock_replenishment_helpers.requests.post')
    @patch('pages.stock_replenishment_helpers.fetch_suppliers')
    def test_save_supplier_created(self, mock_fetch, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response
        
        # Test creating new supplier without products to sidestep the map updating
        success, msg = save_supplier('SUP-001', 'Test Supplier', 'test@example.com', '123456789')
        self.assertTrue(success)
        self.assertIn('created', msg)

    @patch('pages.stock_replenishment_helpers.fetch_suppliers')
    def test_get_next_supplier_id(self, mock_fetch):
        mock_fetch.return_value = [{'supplier_id': 'SUP-001'}, {'supplier_id': 'SUP-005'}]
        next_id = get_next_supplier_id()
        self.assertEqual(next_id, 'SUP-006')

    @patch('pages.stock_replenishment_helpers.EmailSender')
    @patch('pages.stock_replenishment_helpers.save_po_log')
    @patch('pages.stock_replenishment_helpers.update_po_status')
    @patch('pages.stock_replenishment_helpers.st')
    def test_send_po_email_success(self, mock_st, mock_update_po, mock_save_log, mock_email_sender):
        # Setup mock email sender
        mock_instance = mock_email_sender.return_value
        mock_instance.send_supplier_po_email.return_value = (True, "Sent")
        
        mock_update_po.return_value = True
        mock_save_log.return_value = True

        po_row = {
            'po_id': 'PO-123',
            'supplier_id': 'SUP-001',
            'suppliers': {
                'supplier_name': 'Test Supplier',
                'email': 'valid@example.com'
            },
            'replenishment_orders': {
                'product_code': 'P001',
                'suggested_qty': 50
            }
        }
        catalog_map = {'P001': 'Test Product'}
        expected_date = datetime.now()

        # Disable test mode since we want to send to the valid@example.com
        result = send_po_email(po_row, catalog_map, expected_date, test_mode=False)
        self.assertTrue(result)


class TestSupplierDashboard(unittest.TestCase):

    @patch('pages.supplier_dashboard.requests.get')
    def test_fetch_active_pos(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'po_id': 'PO-001'}]
        mock_get.return_value = mock_response

        pos = _fetch_active_pos('SUP-001')
        self.assertEqual(len(pos), 1)
        self.assertEqual(pos[0]['po_id'], 'PO-001')

    @patch('pages.supplier_dashboard.requests.patch')
    @patch('pages.supplier_dashboard.requests.get')
    def test_update_stock_in_catalog(self, mock_get, mock_patch):
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = [{'order_id': 'ORD-123', 'current_stock_level': 10}]
        mock_get.return_value = mock_get_response

        mock_patch_response = MagicMock()
        mock_patch_response.status_code = 200
        mock_patch.return_value = mock_patch_response

        new_stock = _update_stock_in_catalog('P001', 5)
        self.assertEqual(new_stock, 15)
        mock_patch.assert_called_once()


if __name__ == '__main__':
    unittest.main()
