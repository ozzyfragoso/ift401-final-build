
import os
import random
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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

            if user.admin_access:
                return redirect(url_for('admin_dashboard'))

            return redirect(url_for('portfolio'))

        flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/')
@login_required
def home():
    # Each role has its own home page, the same places login sends them
    if current_user.admin_access:
        return redirect(url_for('admin_dashboard'))

    return redirect(url_for('portfolio'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))



MAX_PRICE_CHANGE = 0.01
PRICE_UPDATE_SECONDS = 10
last_price_update = None


def generate_stock_price(current_price):
    current_price = Decimal(str(current_price))
    change_percent = Decimal(
        str(random.uniform(-MAX_PRICE_CHANGE, MAX_PRICE_CHANGE))
    )

    new_price = (
        current_price * (Decimal('1') + change_percent)
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    if new_price == current_price:
        new_price = current_price + (
            Decimal('0.01') if change_percent >= 0 else Decimal('-0.01')
        )

    return max(Decimal('0.01'), new_price)


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

def prices_due_for_update():
    global last_price_update
    now = datetime.now()

    if last_price_update is not None:
        if (now - last_price_update).total_seconds() < PRICE_UPDATE_SECONDS:
            return False

    last_price_update = now
    return True



@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.admin_access:
        flash('Administrator access required.', 'danger')
        return redirect(url_for('portfolio'))

    stocks = Stock.query.order_by(Stock.symbol).all()

    return render_template('admin_dashboard.html', stocks=stocks)


def check_new_stock(symbol, company_name, price_text, shares_text):
    if not symbol or not company_name or not price_text or not shares_text:
        return 'All fields are required.'

    if len(symbol) > 10:
        return 'Ticker must be 10 characters or fewer.'

    if len(company_name) > 100:
        return 'Company name must be 100 characters or fewer.'

    try:
        price = Decimal(price_text)
        shares = int(shares_text)
    except (InvalidOperation, ValueError, OverflowError):
        return 'Enter a valid initial price and number of shares.'

    if not price.is_finite() or price < Decimal('0.01'):
        return 'Initial price must be at least 0.01.'

    if price.as_tuple().exponent < -2:
        return 'Initial price cannot have more than 2 decimal places.'

    if price > Decimal('9999999999999.99'):
        return 'Initial price is too large.'

    if shares < 1 or shares > 2147483647:
        return 'Shares outstanding must be between 1 and 2147483647.'

    if Stock.query.filter_by(symbol=symbol).first():
        return f'Ticker {symbol} is already in use.'

    return None


@app.route('/admin/stocks/create', methods=['GET', 'POST'])
@login_required
def create_stock():
    if not current_user.admin_access:
        flash('Administrator access required.', 'danger')
        return redirect(url_for('portfolio'))

    if request.method == 'POST':
        symbol = request.form.get('symbol', '').strip().upper()
        company_name = request.form.get('company_name', '').strip()
        price_text = request.form.get('current_price', '').strip()
        shares_text = request.form.get('available_quantity', '').strip()

        error = check_new_stock(
            symbol, company_name, price_text, shares_text
        )

        if error:
            flash(error, 'danger')
            return render_template(
                'create_stock.html',
                form_values={
                    'symbol': symbol,
                    'company_name': company_name,
                    'current_price': price_text,
                    'available_quantity': shares_text
                }
            )

        return render_template(
            'confirm_stock.html',
            symbol=symbol,
            company_name=company_name,
            current_price=price_text,
            available_quantity=shares_text
        )

    return render_template('create_stock.html')


@app.route('/admin/stocks/create/confirm', methods=['POST'])
@login_required
def create_stock_confirm():
    if not current_user.admin_access:
        flash('Administrator access required.', 'danger')
        return redirect(url_for('portfolio'))

    symbol = request.form.get('symbol', '').strip().upper()
    company_name = request.form.get('company_name', '').strip()
    price_text = request.form.get('current_price', '').strip()
    shares_text = request.form.get('available_quantity', '').strip()

    error = check_new_stock(
        symbol, company_name, price_text, shares_text
    )

    if error:
        flash(error, 'danger')
        return render_template(
            'create_stock.html',
            form_values={
                'symbol': symbol,
                'company_name': company_name,
                'current_price': price_text,
                'available_quantity': shares_text
            }
        )

    new_stock = Stock(
        symbol=symbol,
        company_name=company_name,
        current_price=Decimal(price_text),
        available_quantity=int(shares_text),
        status='active'
    )

    try:
        db.session.add(new_stock)
        db.session.commit()
        flash('Stock created successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    except Exception:
        db.session.rollback()
        flash('Could not create stock.', 'danger')
        return redirect(url_for('create_stock'))


# Update Stock - Administrator Only
@app.route('/admin/stocks/edit/<int:stock_id>', methods=['GET', 'POST'])
@login_required
def edit_stock(stock_id):
    if not current_user.admin_access:
        flash('Administrator access required.', 'danger')
        return redirect(url_for('portfolio'))

    stock = db.get_or_404(Stock, stock_id)

    if request.method == 'POST':
        try:
            price = Decimal(request.form['current_price'])
            quantity = int(request.form['available_quantity'])
            status = request.form['status']

            if not price.is_finite() or price <= 0 or quantity < 0:
                raise ValueError('Invalid price or quantity')

            if status not in ('active', 'inactive'):
                raise ValueError('Invalid stock status')

            stock.current_price = price
            stock.available_quantity = quantity
            stock.status = status

            db.session.commit()
            flash('Stock updated successfully!', 'success')
            return redirect(url_for('admin_dashboard'))

        except (ValueError, InvalidOperation, KeyError):
            flash('Please enter valid stock information.', 'danger')
        except Exception:
            db.session.rollback()
            flash('Could not update stock.', 'danger')
    return render_template('edit_stock.html', stock=stock)

# Read and validate the market schedule form
def read_schedule_form(form):
    try:
        market_date = datetime.strptime(
            form.get('market_date', ''), '%Y-%m-%d'
        ).date()

        status = form.get('market_status', '')

        if status not in ('open', 'closed', 'holiday'):
            raise ValueError('Invalid market status.')

        open_time = None
        close_time = None

        if status == 'open':
            open_time = datetime.strptime(
                form.get('open_time', ''), '%H:%M'
            ).time()
            close_time = datetime.strptime(
                form.get('close_time', ''), '%H:%M'
            ).time()

            if open_time >= close_time:
                raise ValueError('Opening time must be before closing time.')

        return {
            'market_date': market_date,
            'market_status': status,
            'open_time': open_time,
            'close_time': close_time,
            'notes': form.get('notes', '').strip()
        }

    except ValueError:
        raise ValueError('Enter a valid date, status, and trading hours.')


def save_market_schedule(values):
    schedule = MarketSchedule.query.filter_by(
        market_date=values['market_date']
    ).first()

    if schedule is None:
        schedule = MarketSchedule(
            market_date=values['market_date'],
            admin_id=current_user.user_id
        )
        db.session.add(schedule)

    schedule.market_status = values['market_status']
    schedule.open_time = values['open_time']
    schedule.close_time = values['close_time']
    schedule.notes = values['notes']
    schedule.admin_id = current_user.user_id

    db.session.commit()


@app.route('/admin/market-schedule', methods=['GET', 'POST'])
@login_required
def market_schedule():
    if not current_user.admin_access:
        flash('Administrator access required.', 'danger')
        return redirect(url_for('portfolio'))

    if request.method == 'POST':
        try:
            values = read_schedule_form(request.form)
            save_market_schedule(values)
            flash('Market schedule saved successfully!', 'success')
            return redirect(url_for('market_schedule'))
        except ValueError as error:
            flash(str(error), 'danger')
        except Exception:
            db.session.rollback()
            flash('Could not save market schedule.', 'danger')

    schedules = MarketSchedule.query.order_by(
        MarketSchedule.market_date
    ).all()

    return render_template(
        'market_schedule.html',
        schedules=schedules
    )


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
    try:
        if market_is_open() and prices_due_for_update():
            update_all_stock_prices()

    except Exception:
        app.logger.exception('Stock price generation failed')
        flash('Stock prices could not be updated.', 'warning')

    active_stocks = Stock.query.filter_by(status='active').all()

    # SELL lives on the Portfolio page, so Stocks only needs the stock list
    return render_template('stocks.html', stocks=active_stocks)



def get_portfolio(user_id):
    # Every stock the customer still owns, with its current price
    holdings = Holding.query.filter_by(user_id=user_id).all()

    portfolio = []

    for holding in holdings:
        # Sell deletes a holding at zero shares; this skips any left behind
        if holding.quantity <= 0:
            continue

        # Inactive stocks stay listed, because the customer still owns them
        stock = Stock.query.filter_by(
            stock_id=holding.stock_id
        ).first()

        portfolio.append({
            'symbol': stock.symbol,
            'company_name': stock.company_name,
            'quantity': holding.quantity,
            'current_price': stock.current_price
        })

    # Alphabetical by ticker, as in the Selling stocks mockup
    return sorted(portfolio, key=lambda row: row['symbol'])


def calculate_portfolio_summary(portfolio):
    # Market value of everything the customer owns, at current prices
    holdings_value = Decimal('0.00')

    for row in portfolio:
        holdings_value = (
            holdings_value + row['quantity'] * row['current_price']
        )

    return holdings_value


@app.route('/portfolio')
@login_required
def portfolio():
    customer_portfolio = get_portfolio(current_user.user_id)
    holdings_value = calculate_portfolio_summary(customer_portfolio)

    return render_template(
        'portfolio.html',
        portfolio=customer_portfolio,
        cash_balance=current_user.cash_balance,
        holdings_value=holdings_value
    )


def get_transaction_history(user_id):
    # Every stock trade the customer has made
    transactions = StockTransaction.query.filter_by(user_id=user_id).all()

    # Newest first; trades in the same second stay in the order they were made
    transactions = sorted(
        transactions,
        key=lambda t: (t.transaction_date, t.stock_transaction_id),
        reverse=True
    )

    # Each stock is looked up once, even if it was traded many times
    symbols = {}
    history = []

    for transaction in transactions:
        if transaction.stock_id not in symbols:
            stock = Stock.query.filter_by(
                stock_id=transaction.stock_id
            ).first()
            symbols[transaction.stock_id] = stock.symbol

        # Date and time as in the mockup, e.g. 2026-11-15 1:26 PM
        moment = transaction.transaction_date
        hour = moment.hour % 12 or 12

        history.append({
            'type': transaction.transaction_type.capitalize(),
            'symbol': symbols[transaction.stock_id],
            'quantity': transaction.quantity,
            'price_per_share': transaction.price_per_share,
            'total_amount': transaction.total_amount,
            'date_time': f"{moment:%Y-%m-%d} {hour}:{moment:%M %p}"
        })

    return history


@app.route('/history')
@login_required
def transaction_history():
    history = get_transaction_history(current_user.user_id)

    return render_template('history.html', history=history)


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

    # The customer confirmed a total at the reviewed price; if the price has
    # moved since then, they review the order again instead of paying more or less
    if not price_unchanged(request.form.get('price', ''), stock.current_price):
        flash(
            f'The price of {stock.symbol} changed to '
            f'${stock.current_price:,.2f}. Review your order again.',
            'warning'
        )
        return redirect(url_for('buy_panel', symbol=symbol))

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


def price_unchanged(reviewed_price_text, current_price):
    try:
        return Decimal(reviewed_price_text) == current_price
    except (InvalidOperation, TypeError, ValueError):
        return False


@app.route('/portfolio/<string:symbol>/sell', methods=['GET', 'POST'])
@login_required
def sell_panel(symbol):
    stock = Stock.query.filter_by(
        symbol=symbol
    ).first()

    if stock is None:
        flash('Stock not found.', 'danger')
        return redirect(url_for('portfolio'))

    holding = Holding.query.filter_by(
        user_id=current_user.user_id,
        stock_id=stock.stock_id
    ).first()

    if holding is None or holding.quantity <= 0:
        flash('You do not own shares of this stock.', 'danger')
        return redirect(url_for('portfolio'))

    if not market_is_open():
        flash(
            'Market is closed. Selling is not available.',
            'warning'
        )
        return redirect(url_for('portfolio'))

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


@app.route('/portfolio/<string:symbol>/sell/confirm', methods=['POST'])
@login_required
def sell_stock(symbol):
    try:
        user = db.session.get(
            User,
            current_user.user_id,
            with_for_update=True,
            populate_existing=True
        )

        stock = Stock.query.filter_by(
            symbol=symbol
        ).with_for_update().first()

        if stock is None:
            db.session.rollback()
            flash('Stock is unavailable.', 'danger')
            return redirect(url_for('portfolio'))

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
            return redirect(url_for('portfolio'))

        if quantity is None:
            db.session.rollback()
            flash('Invalid quantity.', 'danger')
            return redirect(url_for('sell_panel', symbol=symbol))

        if holding is None or quantity > holding.quantity:
            db.session.rollback()
            flash('You do not own enough shares.', 'danger')
            return redirect(url_for('portfolio'))

        price = stock.current_price

        if not price_unchanged(request.form.get('price', ''), price):
            db.session.rollback()
            flash(
                f'The price of {stock.symbol} changed to '
                f'${price:,.2f}. Review your order again.',
                'warning'
            )
            return redirect(url_for('sell_panel', symbol=symbol))

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

        shares = 'share' if quantity == 1 else 'shares'

        flash(
            f'Sale complete: Sold {quantity} {shares} of '
            f'{stock.symbol} for ${total:,.2f}.',
            'success'
        )

    except Exception:
        db.session.rollback()
        flash('Sale failed. Please try again.', 'danger')

    return redirect(url_for('portfolio'))
