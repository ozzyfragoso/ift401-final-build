# Stock Trading System

A web application where trainee stockbrokers practice buying and selling simulated stocks, with no real money at risk.

Customers create an account, deposit simulated cash, buy and sell stocks at the current market price while the market is open, and review their portfolio and transaction history. Administrators create stocks, mark them active or inactive, and set the market schedule.

## Tech stack

- **Python** and **Flask** for the web application
- **Flask-SQLAlchemy** (ORM) with **PyMySQL** for the **MySQL** database
- **Flask-Login** and **Flask-Bcrypt** for login and password hashing
- **HTML**, **Jinja2** templates, **Bootstrap** (CDN), and a little CSS and JavaScript

The project follows the course Project Handbook.

## Deployment

The application is fully deployed on AWS:

- **Amazon EC2** (Ubuntu) runs the Flask application on port 8000.
- **Amazon RDS** hosts the MySQL database.
