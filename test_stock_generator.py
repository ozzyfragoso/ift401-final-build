
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

    @patch('app.db.session.commit')
    @patch('app.generate_stock_price')
    @patch('app.Stock.query')
    def test_update_all_active_stocks(
        self, mock_query, mock_generate, mock_commit
    ):
        from unittest.mock import MagicMock
        from app import update_all_stock_prices

        stock = MagicMock()
        stock.current_price = Decimal('100.00')

        mock_query.filter_by.return_value.all.return_value = [stock]
        mock_generate.return_value = Decimal('102.00')

        count = update_all_stock_prices()

        self.assertEqual(count, 1)
        self.assertEqual(stock.current_price, Decimal('102.00'))
        mock_query.filter_by.assert_called_once_with(status='active')
        mock_generate.assert_called_once_with(Decimal('100.00'))
        mock_commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
