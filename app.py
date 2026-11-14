import os
from decimal import Decimal, InvalidOperation
from datetime import datetime, time

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

# Read the database URL and secret key from the .env file, which is not uploaded to GitHub
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



# Models: one class per table in the team ERD


class User(UserMixin, db.Model):
    # Table names follow the ERD (users, stocks, ...) instead of the default singular names
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # bcrypt hash, never plain text
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    # Money is stored as an exact decimal (DECIMAL(15,2) in the ERD) so cents never drift
    cash_balance = db.Column(db.Numeric(15, 2), default=0.00, nullable=False)
    admin_access = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Flask-Login looks for an "id" attribute, but our primary key is called user_id
    def get_id(self):
        return str(self.user_id)


class Stock(db.Model):
    __tablename__ = 'stocks'

    stock_id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), unique=True, nullable=False)
    company_name = db.Column(db.String(100), nullable=False)
    current_price = db.Column(db.Numeric(15, 2), nullable=False)
    available_quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False)  # active or inactive


class Holding(db.Model):
    __tablename__ = 'holdings'
    # A customer has at most one row per stock, so a second purchase updates the existing row
    __table_args__ = (db.UniqueConstraint('user_id', 'stock_id'),)

    holding_id = db.Column(db.Integer, primary_key=True)
    # ForeignKey ties each holding to its owner and its stock
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.stock_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    average_price = db.Column(db.Numeric(15, 2), nullable=False)


class StockTransaction(db.Model):
    __tablename__ = 'stock_transactions'

    stock_transaction_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.stock_id'), nullable=False)
    # Only 'buy' or 'sell' are allowed
    transaction_type = db.Column(db.Enum('buy', 'sell', name='stock_transaction_type'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_per_share = db.Column(db.Numeric(15, 2), nullable=False)
    total_amount = db.Column(db.Numeric(15, 2), nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.now, nullable=False)


class CashTransaction(db.Model):
    __tablename__ = 'cash_transactions'

    cash_transaction_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # deposit or withdraw
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    description = db.Column(db.String(255))


class MarketSchedule(db.Model):
    __tablename__ = 'market_schedule'

    schedule_id = db.Column(db.Integer, primary_key=True)
    # The administrator who set this schedule; the route checks that this user has admin_access
    admin_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    # One row per calendar date; holiday and closed rows can leave the times empty
    market_date = db.Column(db.Date, unique=True, nullable=False)
    open_time = db.Column(db.Time)
    close_time = db.Column(db.Time)
    market_status = db.Column(db.Enum('open', 'closed', 'holiday', name='market_status'), nullable=False)
    notes = db.Column(db.String(255))


with app.app_context():
    db.create_all()


# Flask-Login calls this to find the logged-in user from the id stored in the session
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


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

        if user.admin_access:
            return redirect(url_for('admin_dashboard'))
        else:
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
    <a href="/logout">Logout</a>
    """


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


# Administrator Dashboard
# Administrator Dashboard
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.admin_access:
        flash('Administrator access required.', 'danger')
        return redirect(url_for('dashboard'))

    return render_template('admin_dashboard.html')

# Create Stock - Administrator Only
@app.route('/admin/stocks/create', methods=['GET', 'POST'])
@login_required
def create_stock():
    if not current_user.admin_access:
        flash('Administrator access required.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        symbol = request.form.get('symbol', '').strip().upper()
        company_name = request.form.get('company_name', '').strip()
        status = request.form.get('status', '')

        try:
            price = Decimal(request.form.get('current_price', ''))
            quantity = int(request.form.get('available_quantity', ''))
        except (InvalidOperation, ValueError):
            flash('Enter a valid price and quantity.', 'danger')
            return redirect(url_for('create_stock'))

        if not symbol or not company_name:
            flash('All fields are required.', 'danger')
            return redirect(url_for('create_stock'))

        if not price.is_finite() or price <= 0 or price > Decimal('9999999999999.99'):
            flash('Enter a valid stock price.', 'danger')
            return redirect(url_for('create_stock'))

        if quantity < 0 or quantity > 2147483647:
            flash('Enter a valid stock quantity.', 'danger')
            return redirect(url_for('create_stock'))

        if status not in ('active', 'inactive'):
            flash('Invalid stock status.', 'danger')
            return redirect(url_for('create_stock'))

        if Stock.query.filter_by(symbol=symbol).first():
            flash('Stock symbol already exists.', 'danger')
            return redirect(url_for('create_stock'))

        new_stock = Stock(
            symbol=symbol,
            company_name=company_name,
            current_price=price,
            available_quantity=quantity,
            status=status
        )

        try:
            db.session.add(new_stock)
            db.session.commit()
            flash('Stock created successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception:
            db.session.rollback()
            flash('Could not create stock.', 'danger')

    return render_template('create_stock.html')

# Stock Inventory - Administrator Only
@app.route('/admin/stocks')
@login_required
def stock_inventory():
    if not current_user.admin_access:
        flash('Administrator access required.', 'danger')
        return redirect(url_for('dashboard'))

    stocks = Stock.query.order_by(Stock.symbol).all()

    return render_template('stock_inventory.html', stocks=stocks)

# Market Schedule - Administrator Only
@app.route('/admin/market-schedule', methods=['GET', 'POST'])
@login_required
def market_schedule():
    if not current_user.admin_access:
        flash('Administrator access required.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            market_date = datetime.strptime(
                request.form.get('market_date', ''), '%Y-%m-%d'
            ).date()

            status = request.form.get('market_status', '')

            if status not in ('open', 'closed', 'holiday'):
                flash('Invalid market status.', 'danger')
                return redirect(url_for('market_schedule'))

            open_value = request.form.get('open_time', '')
            close_value = request.form.get('close_time', '')

            open_time = (
                datetime.strptime(open_value, '%H:%M').time()
                if open_value else None
            )
            close_time = (
                datetime.strptime(close_value, '%H:%M').time()
                if close_value else None
            )

            if status == 'open':
                if not open_time or not close_time or open_time >= close_time:
                    flash('Enter valid opening and closing times.', 'danger')
                    return redirect(url_for('market_schedule'))
            else:
                open_time = None
                close_time = None

        except ValueError:
            flash('Enter a valid date and time.', 'danger')
            return redirect(url_for('market_schedule'))

        if MarketSchedule.query.filter_by(market_date=market_date).first():
            flash('A schedule already exists for this date.', 'danger')
            return redirect(url_for('market_schedule'))

        schedule = MarketSchedule(
            admin_id=current_user.user_id,
            market_date=market_date,
            open_time=open_time,
            close_time=close_time,
            market_status=status,
            notes=request.form.get('notes', '').strip()
        )

        try:
            db.session.add(schedule)
            db.session.commit()
            flash('Market schedule saved successfully!', 'success')
            return redirect(url_for('market_schedule'))
        except Exception:
            db.session.rollback()
            flash('Could not save market schedule.', 'danger')



    schedules = MarketSchedule.query.order_by(
        MarketSchedule.market_date
    ).all()

    return render_template('market_schedule.html', schedules=schedules)

# Edit Market Schedule - Administrator Only
@app.route('/admin/market-schedule/edit/<int:schedule_id>',
           methods=['GET', 'POST'])
@login_required
def edit_market_schedule(schedule_id):
    if not current_user.admin_access:
        flash('Administrator access required.', 'danger')
        return redirect(url_for('dashboard'))

    schedule = db.get_or_404(MarketSchedule, schedule_id)

    if request.method == 'POST':
        try:
            status = request.form.get('market_status', '')
            if status not in ('open', 'closed', 'holiday'):
                raise ValueError('Invalid status')

            open_value = request.form.get('open_time', '')
            close_value = request.form.get('close_time', '')

            open_time = (
                datetime.strptime(open_value, '%H:%M').time()
                if open_value else None
            )
            close_time = (
                datetime.strptime(close_value, '%H:%M').time()
                if close_value else None
            )

            if status == 'open':
                if not open_time or not close_time or open_time >= close_time:
                    raise ValueError('Invalid trading hours')
            else:
                open_time = None
                close_time = None

        except ValueError:
            flash('Please enter valid market hours and status.', 'danger')
            return redirect(url_for('edit_market_schedule',
                                    schedule_id=schedule_id))

        schedule.open_time = open_time
        schedule.close_time = close_time
        schedule.market_status = status
        schedule.notes = request.form.get('notes', '').strip()

        try:
            db.session.commit()
            flash('Market schedule updated successfully!', 'success')
            return redirect(url_for('market_schedule'))
        except Exception:
            db.session.rollback()
            flash('Could not update market schedule.', 'danger')

    return render_template('edit_market_schedule.html',
                           schedule=schedule)








    if not current_user.admin_access:
        flash('Administrator access required.', 'danger')
        return redirect(url_for('dashboard'))

    return render_template('admin_dashboard.html')




# Buy Stock


def market_is_open():
    now = datetime.now()
    schedule = MarketSchedule.query.filter_by(market_date=now.date()).first()

    # An administrator's schedule for today always wins over the default hours
    if schedule:
        if schedule.market_status != 'open':
            return False
        if schedule.open_time is None or schedule.close_time is None:
            return False
        return schedule.open_time <= now.time() < schedule.close_time

    # No schedule for today: the default is Monday to Friday, 9:00 AM to 5:00 PM
    return now.weekday() < 5 and time(9, 0) <= now.time() < time(17, 0)


def read_quantity(quantity_text):
    # Shares are bought in whole numbers, at least 1; anything else (0, -5, 2.5, "ten") is rejected
    if quantity_text.isdigit() and int(quantity_text) >= 1:
        return int(quantity_text)
    return None


def validate_funds(user, total):
    return user.cash_balance >= total


def update_cash_balance(user, amount):
    # Buy passes a negative amount (money out), Sell a positive one (money in)
    user.cash_balance = user.cash_balance + amount


def update_stock_inventory(stock, change):
    # Buy passes a negative change (shares leave the inventory), Sell a positive one
    stock.available_quantity = stock.available_quantity + change


def update_holding(user_id, stock_id, quantity, price):
    holding = Holding.query.filter_by(user_id=user_id, stock_id=stock_id).first()

    if holding:
        # Weighted average: what all the shares cost together, divided by how many there are now
        total_cost = holding.quantity * holding.average_price + quantity * price
        holding.quantity = holding.quantity + quantity
        holding.average_price = round(total_cost / holding.quantity, 2)
    else:
        new_holding = Holding(user_id=user_id, stock_id=stock_id, quantity=quantity, average_price=price)
        db.session.add(new_holding)


def record_stock_transaction(user_id, stock_id, transaction_type, quantity, price, total):
    # transaction_date is filled in automatically with the current date and time
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
    # Returns the reason the order cannot go through, or None when it can
    if quantity is None:
        return 'Enter a whole number of shares, 1 or more.'
    if quantity > stock.available_quantity:
        return f'Only {stock.available_quantity} shares of {stock.symbol} are available.'
    total = quantity * stock.current_price
    if not validate_funds(current_user, total):
        return f'Insufficient funds. This purchase costs ${total:,.2f} and your cash balance is ${current_user.cash_balance:,.2f}.'
    return None


# Screen 1: every active stock with its price and a BUY button
@app.route('/stocks')
@login_required
def stocks():
    active_stocks = Stock.query.filter_by(status='active').all()
    return render_template('stocks.html', stocks=active_stocks)


# Screen 2: the Buy panel. GET shows the quantity form; POST checks the order and asks for confirmation
@app.route('/stocks/<string:symbol>/buy', methods=['GET', 'POST'])
@login_required
def buy_panel(symbol):
    stock = Stock.query.filter_by(symbol=symbol, status='active').first()
    if not stock:
        flash('That stock is not available.', 'danger')
        return redirect(url_for('stocks'))

    # The BUY buttons are always shown, so the market check happens here, after a stock is selected
    if not market_is_open():
        flash('Market is closed.', 'warning')
        return redirect(url_for('stocks'))

    if request.method == 'POST':
        quantity = read_quantity(request.form['quantity'].strip())
        problem = check_buy_order(stock, quantity)
        if problem:
            flash(problem, 'danger')
            return redirect(url_for('buy_panel', symbol=symbol))

        total = quantity * stock.current_price
        return render_template('buy.html', stock=stock, quantity=quantity, total=total)

    return render_template('buy.html', stock=stock, quantity=None, total=None)


# Runs only after the customer selects Yes; a purchase cannot be cancelled once this commits
@app.route('/stocks/<string:symbol>/buy/confirm', methods=['POST'])
@login_required
def buy_stock(symbol):
    stock = Stock.query.filter_by(symbol=symbol, status='active').first()
    if not stock:
        flash('That stock is not available.', 'danger')
        return redirect(url_for('stocks'))

    # Check everything again: the market may have closed or the balance changed since the panel loaded
    if not market_is_open():
        flash('Market is closed.', 'warning')
        return redirect(url_for('stocks'))

    quantity = read_quantity(request.form['quantity'].strip())
    problem = check_buy_order(stock, quantity)
    if problem:
        flash(problem, 'danger')
        return redirect(url_for('buy_panel', symbol=symbol))

    price = stock.current_price
    total = quantity * price

    # All four changes are saved together in one commit, or none of them are
    try:
        update_cash_balance(current_user, -total)
        update_holding(current_user.user_id, stock.stock_id, quantity, price)
        update_stock_inventory(stock, -quantity)
        record_stock_transaction(current_user.user_id, stock.stock_id, 'buy', quantity, price, total)
        db.session.commit()
        shares = 'share' if quantity == 1 else 'shares'
        flash(f'Purchase complete: {quantity} {shares} of {stock.symbol} for ${total:,.2f}.', 'success')
    except Exception:
        db.session.rollback()
        flash('The purchase could not be completed. Nothing was charged. Please try again.', 'danger')

    return redirect(url_for('stocks'))



if __name__ == '__main__':
    app.run(debug=True)
