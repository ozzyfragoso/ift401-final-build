
import unittest
from decimal import Decimal
from unittest.mock import patch

from app import generate_stock_price


class TestStockGenerator(unittest.TestCase):

    @patch('app.random.uniform', return_value=0.05)
    def test_price_increase(self, mock_random):
        result = generate_stock_price(Decimal('100.00'))
        self.assertEqual(result, Decimal('105.00'))

    @patch('app.random.uniform', return_value=-0.05)
    def test_price_decrease(self, mock_random):
        result = generate_stock_price(Decimal('100.00'))
        self.assertEqual(result, Decimal('95.00'))

    @patch('app.random.uniform', return_value=-0.05)
    def test_minimum_price(self, mock_random):
        result = generate_stock_price(Decimal('0.01'))
        self.assertEqual(result, Decimal('0.01'))

    @patch('app.random.uniform', return_value=0.01234)
    def test_decimal_rounding(self, mock_random):
        result = generate_stock_price(Decimal('100.00'))
        self.assertEqual(result, Decimal('101.23'))


if __name__ == '__main__':
    unittest.main()
