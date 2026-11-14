
import os
import random
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, time

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

load_dotenv()

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    cash_balance = db.Column(db.Numeric(15, 2), default=0.00, nullable=False)
    admin_access = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    def get_id(self):
        return str(self.user_id)


class Stock(db.Model):
    __tablename__ = 'stocks'

    stock_id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), unique=True, nullable=False)
    company_name = db.Column(db.String(100), nullable=False)
    current_price = db.Column(db.Numeric(15, 2), nullable=False)
    available_quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False)


class Holding(db.Model):
    __tablename__ = 'holdings'
    __table_args__ = (db.UniqueConstraint('user_id', 'stock_id'),)

    holding_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.stock_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    average_price = db.Column(db.Numeric(15, 2), nullable=False)


class StockTransaction(db.Model):
    __tablename__ = 'stock_transactions'

    stock_transaction_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.stock_id'), nullable=False)
    transaction_type = db.Column(db.Enum('buy', 'sell', name='stock_transaction_type'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_per_share = db.Column(db.Numeric(15, 2), nullable=False)
    total_amount = db.Column(db.Numeric(15, 2), nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.now, nullable=False)


class CashTransaction(db.Model):
    __tablename__ = 'cash_transactions'

    cash_transaction_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    description = db.Column(db.String(255))


class MarketSchedule(db.Model):
    __tablename__ = 'market_schedule'

    schedule_id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    market_date = db.Column(db.Date, unique=True, nullable=False)
    open_time = db.Column(db.Time)
    close_time = db.Column(db.Time)
    market_status = db.Column(db.Enum('open', 'closed', 'holiday', name='market_status'), nullable=False)
    notes = db.Column(db.String(255))


with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name'].strip()
        last_name = request.form['last_name'].strip()
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if not all([first_name, last_name, username, email, password]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(
            password
        ).decode('utf-8')

        new_user = User(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            password=hashed_password,
            cash_balance=0,
            admin_access=False
        )

        try:
            db.session.add(new_user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'danger')
            return redirect(url_for('register'))

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/')
@login_required
def dashboard():
    return f"""
    <h2>Stock Trading System</h2>
    <p>Welcome, {current_user.username}!</p>
    <p>You have successfully logged in.</p>
    <a href="/stocks">View Stocks</a>
    <br>
    <a href="/logout">Logout</a>
    """


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

def generate_stock_price(current_price):
    current_price = Decimal(str(current_price))
    change_percent = Decimal(str(random.uniform(-0.05, 0.05)))
    new_price = current_price * (Decimal('1') + change_percent)

    return max(
        Decimal('0.01'),
        new_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    )
def update_all_stock_prices():
    active_stocks = Stock.query.filter_by(status='active').all()

    try:
        for stock in active_stocks:
            stock.current_price = generate_stock_price(
                stock.current_price
            )

        db.session.commit()
        return len(active_stocks)

    except Exception:
        db.session.rollback()
        raise
def market_is_open():
    now = datetime.now()
    schedule = MarketSchedule.query.filter_by(
        market_date=now.date()
    ).first()

    if schedule:
        if schedule.market_status != 'open':
            return False

        if schedule.open_time is None or schedule.close_time is None:
            return False

        return schedule.open_time <= now.time() < schedule.close_time

    return now.weekday() < 5 and time(9, 0) <= now.time() < time(17, 0)


def read_quantity(quantity_text):
    if quantity_text.isdigit() and int(quantity_text) >= 1:
        return int(quantity_text)

    return None


def validate_funds(user, total):
    return user.cash_balance >= total


def update_cash_balance(user, amount):
    user.cash_balance = user.cash_balance + amount


def update_stock_inventory(stock, change):
    stock.available_quantity = stock.available_quantity + change


def update_holding(user_id, stock_id, quantity, price):
    holding = Holding.query.filter_by(
        user_id=user_id,
        stock_id=stock_id
    ).first()

    if holding:
        total_cost = (
            holding.quantity * holding.average_price
            + quantity * price
        )

        holding.quantity = holding.quantity + quantity
        holding.average_price = round(
            total_cost / holding.quantity, 2
        )
    else:
        new_holding = Holding(
            user_id=user_id,
            stock_id=stock_id,
            quantity=quantity,
            average_price=price
        )

        db.session.add(new_holding)


def record_stock_transaction(
    user_id,
    stock_id,
    transaction_type,
    quantity,
    price,
    total
):
    transaction = StockTransaction(
        user_id=user_id,
        stock_id=stock_id,
        transaction_type=transaction_type,
        quantity=quantity,
        price_per_share=price,
        total_amount=total
    )

    db.session.add(transaction)


def check_buy_order(stock, quantity):
    if quantity is None:
        return 'Enter a whole number of shares, 1 or more.'

    if quantity > stock.available_quantity:
        return (
            f'Only {stock.available_quantity} shares '
            f'of {stock.symbol} are available.'
        )

    total = quantity * stock.current_price

    if not validate_funds(current_user, total):
        return (
            f'Insufficient funds. This purchase costs '
            f'${total:,.2f} and your cash balance is '
            f'${current_user.cash_balance:,.2f}.'
        )

    return None


@app.route('/stocks')
@login_required
def stocks():
    active_stocks = Stock.query.filter_by(
        status='active'
    ).all()

    holdings = Holding.query.filter(
        Holding.user_id == current_user.user_id,
        Holding.quantity > 0
    ).all()

    owned_stock_ids = {
        holding.stock_id for holding in holdings
    }

    return render_template(
        'stocks.html',
        stocks=active_stocks,
        owned_stock_ids=owned_stock_ids
    )


@app.route('/stocks/<string:symbol>/buy', methods=['GET', 'POST'])
@login_required
def buy_panel(symbol):
    stock = Stock.query.filter_by(
        symbol=symbol,
        status='active'
    ).first()

    if not stock:
        flash('That stock is not available.', 'danger')
        return redirect(url_for('stocks'))

    if not market_is_open():
        flash('Market is closed.', 'warning')
        return redirect(url_for('stocks'))

    if request.method == 'POST':
        quantity = read_quantity(
            request.form.get('quantity', '').strip()
        )

        problem = check_buy_order(stock, quantity)

        if problem:
            flash(problem, 'danger')
            return redirect(url_for('buy_panel', symbol=symbol))

        total = quantity * stock.current_price

        return render_template(
            'buy.html',
            stock=stock,
            quantity=quantity,
            total=total
        )

    return render_template(
        'buy.html',
        stock=stock,
        quantity=None,
        total=None
    )


@app.route('/stocks/<string:symbol>/buy/confirm', methods=['POST'])
@login_required
def buy_stock(symbol):
    stock = Stock.query.filter_by(
        symbol=symbol,
        status='active'
    ).first()

    if not stock:
        flash('That stock is not available.', 'danger')
        return redirect(url_for('stocks'))

    if not market_is_open():
        flash('Market is closed.', 'warning')
        return redirect(url_for('stocks'))

    quantity = read_quantity(
        request.form.get('quantity', '').strip()
    )

    problem = check_buy_order(stock, quantity)

    if problem:
        flash(problem, 'danger')
        return redirect(url_for('buy_panel', symbol=symbol))

    price = stock.current_price
    total = quantity * price

    try:
        update_cash_balance(current_user, -total)

        update_holding(
            current_user.user_id,
            stock.stock_id,
            quantity,
            price
        )

        update_stock_inventory(stock, -quantity)

        record_stock_transaction(
            current_user.user_id,
            stock.stock_id,
            'buy',
            quantity,
            price,
            total
        )

        db.session.commit()

        shares = 'share' if quantity == 1 else 'shares'

        flash(
            f'Purchase complete: {quantity} {shares} '
            f'of {stock.symbol} for ${total:,.2f}.',
            'success'
        )

    except Exception:
        db.session.rollback()
        flash(
            'The purchase could not be completed. '
            'Nothing was charged. Please try again.',
            'danger'
        )

    return redirect(url_for('stocks'))


@app.route('/stocks/<string:symbol>/sell', methods=['GET', 'POST'])
@login_required
def sell_panel(symbol):
    stock = Stock.query.filter_by(
        symbol=symbol,
        status='active'
    ).first()

    if stock is None:
        flash('Stock not found.', 'danger')
        return redirect(url_for('stocks'))

    holding = Holding.query.filter_by(
        user_id=current_user.user_id,
        stock_id=stock.stock_id
    ).first()

    if holding is None or holding.quantity <= 0:
        flash('You do not own shares of this stock.', 'danger')
        return redirect(url_for('stocks'))

    if not market_is_open():
        flash(
            'Market is closed. Selling is not available.',
            'warning'
        )
        return redirect(url_for('stocks'))

    if request.method == 'POST':
        quantity = read_quantity(
            request.form.get('quantity', '').strip()
        )

        if quantity is None:
            flash('Enter a valid positive whole number.', 'danger')
            return redirect(url_for('sell_panel', symbol=symbol))

        if quantity > holding.quantity:
            flash(
                'You cannot sell more shares than you own.',
                'danger'
            )
            return redirect(url_for('sell_panel', symbol=symbol))

        total = quantity * stock.current_price

        return render_template(
            'sell.html',
            stock=stock,
            holding=holding,
            quantity=quantity,
            total=total
        )

    return render_template(
        'sell.html',
        stock=stock,
        holding=holding,
        quantity=None,
        total=None
    )


@app.route('/stocks/<string:symbol>/sell/confirm', methods=['POST'])
@login_required
def sell_stock(symbol):
    try:
        user = db.session.get(
            User,
            current_user.user_id,
            with_for_update=True
        )

        stock = Stock.query.filter_by(
            symbol=symbol,
            status='active'
        ).with_for_update().first()

        if stock is None:
            db.session.rollback()
            flash('Stock is unavailable.', 'danger')
            return redirect(url_for('stocks'))

        holding = Holding.query.filter_by(
            user_id=user.user_id,
            stock_id=stock.stock_id
        ).with_for_update().first()

        quantity = read_quantity(
            request.form.get('quantity', '').strip()
        )

        if not market_is_open():
            db.session.rollback()
            flash('Market is closed.', 'warning')
            return redirect(url_for('stocks'))

        if quantity is None:
            db.session.rollback()
            flash('Invalid quantity.', 'danger')
            return redirect(url_for('sell_panel', symbol=symbol))

        if holding is None or quantity > holding.quantity:
            db.session.rollback()
            flash('You do not own enough shares.', 'danger')
            return redirect(url_for('stocks'))

        price = stock.current_price
        total = quantity * price

        update_cash_balance(user, total)
        update_stock_inventory(stock, quantity)

        holding.quantity -= quantity

        if holding.quantity == 0:
            db.session.delete(holding)

        record_stock_transaction(
            user.user_id,
            stock.stock_id,
            'sell',
            quantity,
            price,
            total
        )

        db.session.commit()

        flash(
            f'Sale complete: Sold {quantity} shares of '
            f'{stock.symbol} for ${total:,.2f}.',
            'success'
        )

    except Exception:
        db.session.rollback()
        app.logger.exception('Sell Stock transaction failed')
        flash('Sale failed. Please try again.', 'danger')

    return redirect(url_for('stocks'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
