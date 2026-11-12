import os
from datetime import datetime

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
