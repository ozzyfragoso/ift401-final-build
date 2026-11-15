
import os

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SECRET_KEY'] = 'test-only'

import unittest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import app as stock_app
from app import (
    app,
    db,
    Stock,
    User,
    generate_stock_price,
    update_all_stock_prices
)


class TestStockGenerator(unittest.TestCase):

    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        stock_app.last_price_update = None

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('app.random.uniform', return_value=0.01)
    def test_price_increase(self, mock_random):
        result = generate_stock_price(Decimal('100.00'))
        self.assertEqual(result, Decimal('101.00'))

    @patch('app.random.uniform', return_value=-0.01)
    def test_price_decrease(self, mock_random):
        result = generate_stock_price(Decimal('100.00'))
        self.assertEqual(result, Decimal('99.00'))

    @patch('app.random.uniform', return_value=-0.01)
    def test_minimum_price(self, mock_random):
        result = generate_stock_price(Decimal('0.01'))
        self.assertEqual(result, Decimal('0.01'))

    @patch('app.random.uniform', return_value=0.001234)
    def test_decimal_rounding(self, mock_random):
        result = generate_stock_price(Decimal('100.00'))
        self.assertEqual(result, Decimal('100.12'))

    @patch('app.random.uniform', return_value=0.005)
    def test_penny_stock_increases(self, mock_random):
        result = generate_stock_price(Decimal('0.09'))
        self.assertEqual(result, Decimal('0.10'))

    @patch('app.random.uniform', return_value=-0.005)
    def test_penny_stock_decreases(self, mock_random):
        result = generate_stock_price(Decimal('0.09'))
        self.assertEqual(result, Decimal('0.08'))

    def test_active_stocks_update_in_database(self):
        active_stock = Stock(
            symbol='ABC',
            company_name='Active Company',
            current_price=Decimal('100.00'),
            available_quantity=100,
            status='active'
        )

        inactive_stock = Stock(
            symbol='XYZ',
            company_name='Inactive Company',
            current_price=Decimal('100.00'),
            available_quantity=100,
            status='inactive'
        )

        db.session.add_all([active_stock, inactive_stock])
        db.session.commit()

        with patch('app.random.uniform', return_value=0.01):
            count = update_all_stock_prices()

        db.session.expire_all()

        active = Stock.query.filter_by(symbol='ABC').first()
        inactive = Stock.query.filter_by(symbol='XYZ').first()

        self.assertEqual(count, 1)
        self.assertEqual(active.current_price, Decimal('101.00'))
        self.assertEqual(inactive.current_price, Decimal('100.00'))

    def test_ten_second_limit(self):
        self.assertTrue(stock_app.prices_due_for_update())
        self.assertFalse(stock_app.prices_due_for_update())

        stock_app.last_price_update -= timedelta(seconds=9)
        self.assertFalse(stock_app.prices_due_for_update())

        stock_app.last_price_update -= timedelta(seconds=2)
        self.assertTrue(stock_app.prices_due_for_update())

    @patch('app.db.session.rollback')
    @patch('app.db.session.commit', side_effect=Exception('Database error'))
    @patch('app.generate_stock_price', return_value=Decimal('101.00'))
    @patch('app.Stock.query')
    def test_database_failure_rolls_back(
        self,
        mock_query,
        mock_generate,
        mock_commit,
        mock_rollback
    ):
        stock = MagicMock()
        stock.current_price = Decimal('100.00')

        mock_query.filter_by.return_value.all.return_value = [stock]

        with self.assertRaises(Exception):
            update_all_stock_prices()

        mock_query.filter_by.assert_called_once_with(status='active')
        mock_commit.assert_called_once()
        mock_rollback.assert_called_once()

    @patch('app.update_all_stock_prices')
    @patch('app.market_is_open', return_value=True)
    def test_second_stocks_view_does_not_update(
        self,
        mock_market,
        mock_update
    ):
        user = User(
            username='testuser',
            password='testpassword',
            first_name='Test',
            last_name='User',
            email='test@example.com',
            cash_balance=Decimal('1000.00'),
            admin_access=False
        )

        db.session.add(user)
        db.session.commit()

        with app.test_client() as client:
            with client.session_transaction() as session:
                session['_user_id'] = str(user.user_id)
                session['_fresh'] = True

            with patch('app.render_template', return_value='Stocks page'):
                first = client.get('/stocks')
                second = client.get('/stocks')

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        mock_update.assert_called_once()

    @patch('app.update_all_stock_prices')
    @patch('app.market_is_open', return_value=False)
    def test_market_closed_prevents_updates(
        self,
        mock_market,
        mock_update
    ):
        user = User(
            username='closeduser',
            password='testpassword',
            first_name='Closed',
            last_name='User',
            email='closed@example.com',
            cash_balance=Decimal('1000.00'),
            admin_access=False
        )

        db.session.add(user)
        db.session.commit()

        with app.test_client() as client:
            with client.session_transaction() as session:
                session['_user_id'] = str(user.user_id)
                session['_fresh'] = True

            with patch('app.render_template', return_value='Stocks page'):
                response = client.get('/stocks')

        self.assertEqual(response.status_code, 200)
        mock_update.assert_not_called()


if __name__ == '__main__':
    unittest.main()
