# Stock Trading System

A web application where trainee stockbrokers practice buying and selling simulated stocks, with no real money at risk.

Customers create an account, deposit simulated cash, buy and sell stocks at the current market price while the market is open, and review their portfolio and transaction history. Administrators create stocks and set the market schedule.

## Tech stack

- **Python** and **Flask** for the web application
- **Flask-SQLAlchemy** (ORM) with **PyMySQL** for the **MySQL** database
- **Flask-Login** and **Flask-Bcrypt** for login and password hashing
- **HTML**, **Jinja2** templates, **Bootstrap** (CDN), and a little CSS and JavaScript

The project follows the course Project Handbook. It runs locally first and is deployed to AWS (RDS and EC2) at the end.

## Features

| Feature | Status |
|---|---|
| Login and registration | Planned |
| Admin dashboard and market schedule | Planned |
| Buy stock | In progress |
| Sell stock | Planned |
| Random stock price generator | Planned |
| Transaction history | Planned |
| Profit/loss tracking (extra) | Planned |
| Live stock price chart (extra) | Planned |

## Getting started


1. Create a folder for the project and clone this repository into it, so the structure looks like this:

   ```
   your_root_folder/
   ├── venv/
   └── ift401-final-build/     (this repository)
   ```

2. In `your_root_folder`, create and activate a virtual environment:

   ```
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install the packages:

   ```
   pip install -r ift401-final-build\requirements.txt
   ```

4. In MySQL Workbench, create an empty schema named `stock_trading`.

5. In the repository folder, copy `.env.example` to `.env` and fill in your own MySQL password and a long random secret key. The `.env` file holds private values and is never uploaded to GitHub.

6. Start the app from the repository folder