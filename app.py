from datetime import datetime, timedelta
import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd


# Configure application

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "a_fallback_default_key")

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]

    # 1. Get the user's net stocks and shares
    rows = db.execute("""
            SELECT ROW_NUMBER() over() As number, symbol,
                SUM(CASE WHEN type = 'bought' THEN shares ELSE -shares END) AS total_shares
            FROM transactions
            WHERE user_id = ?
            GROUP BY symbol
            HAVING total_shares > 0
        """, user_id)

    # 2. Build a list of dictionaries with LIVE prices
    print(rows)
    portfolio = []
    stocks_total_value = 0

    for row in rows:
        stock_info = lookup(row["symbol"])
        current_price = stock_info["price"]
        total_value = row["total_shares"] * current_price
        stocks_total_value += total_value

        portfolio.append({
            "symbol": row["symbol"],
            "shares": row["total_shares"],
            "price": current_price,
            "total": total_value
        })

    # 3. Get the user's current available cash
    user_cash_row = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = user_cash_row[0]["cash"]

    # 4. Calculate the grand total (cash + stocks_total_value)
    grand_total = stocks_total_value + cash

    print(portfolio)
    print("We are brothers and sisters.")

    destination = {'Bank': ['Gemini society development bank', 'Google fun bank', 'Sundharaa Agriculture baink'],
                   'E-wallet': ['nepal_SBI', 'e-sewa', 'khalti'],
                   'Crypto': ['GOOD', 'BAD', 'UGLY'],
                   'Donate': ['Buy me a coffe', 'Pateron', 'GoFundMe', 'SBSK family', 'Bayyinah gift']}
    return render_template("index.html", portfolio=portfolio, cash=cash, grand_total=grand_total, stocks_total_value=stocks_total_value, destination=destination)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares_input = request.form.get("shares")

        # 1)Basic validation
        if not symbol:
            return apology("symbol is required")

        # Check if shares is a positive integer
        try:
            shares = int(shares_input)
            if (shares <= 0):
                return apology("shares must be positive number")
        except ValueError:
            return apology("shares must be positive number")

        # 2)stock validation
        stock = lookup(symbol)
        if not stock:
            return apology("Invalid stock")

        # 3. Affordibility check
        user_id = session["user_id"]

        # will return a dictionary like [{'cash' : 10000}]
        rows = db.execute("SELECT * FROM USERS WHERE id = ?", user_id)
        cash = rows[0]['cash']

        total_cost = shares * stock['price']

        if cash < total_cost:
            return apology("Insufficient balance to buy")

        else:
            # 4. Transactions

            # update cash
            db.execute("UPDATE users SET cash = cash - ?  WHERE id = ?", total_cost, user_id)

            # record the purchase in single transaction table
            db.execute("""
               INSERT INTO transactions(user_id, symbol, shares, price, type)
                VALUES(?, ?, ?, ?, ?)
                """, user_id,  stock['symbol'], shares, stock["price"], "bought")

            flash("Bought {} shares per {} with {}".format(shares, stock["price"], usd(total_cost)))
            return redirect("/")
    else:
        return render_template("buy_shares.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]

    history_table = db.execute(
        "SELECT ROW_NUMBER() over() As number, type, symbol, shares, price, shares*price AS total, timestamp FROM transactions WHERE user_id = ?", user_id)
    print(history_table)
    return render_template("history_shares.html", history_table=history_table)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    symbol = request.form.get("symbol")

    # if user submitted
    if request.method == "POST":
        if not symbol:
            return apology("Error:type stock symbol to get the stock quote", "400")

        # stroing stock quote dictionary
        quote = lookup(symbol)

        # if stock symbol was not in database
        if quote == None:
            return apology("Error: Incorrect stock symbol or is not available")

        # can display the stock quotes
        return render_template("quoted.html", quote=quote)

    # Get method. front end. render interface
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        re_password = request.form.get("confirmation")
        country = request.form.get("country")
        district = request.form.get("district")

        # Check if user left username/password field blank
        if not username or not password:
            return apology("Error: Username/password was set blank", "400")

        # Check if password and re-password match or not.
        if not password == re_password:
            return apology("Error: password does not match", "400")

        # Check if username already taken or not, save hashed version of user password and save to users database
        try:
            db.execute("INSERT INTO users(username, hash)  VALUES(?,?)",
                       username, generate_password_hash(password))
            return redirect("/login")

        except ValueError:
            return apology("Error: Username already taken")
    else:
        return render_template("register.html", province_map=province_map)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user_id = session["user_id"]

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        current_price = lookup(symbol)
        sell_amount = int(shares) * current_price['price']
        cash = db.execute("SELECT cash FROM users WHERE id =  ?", user_id)

        owned_shares = db.execute(
            "SELECT SUM(CASE WHEN type='bought' THEN shares ELSE -shares END) AS shares FROM transactions  WHERE  user_id = ? AND symbol = ?", user_id, symbol.upper())

        # -> Server side validation
        # 1. blank entry
        if not symbol or not shares:
            return apology("Error: stock symbol/shares missing")

        if int(shares) <= 0:
            return apology("Error: shares need to be positive number")

        print('owned shares is {}'.format(owned_shares))
        # 2. Insufficient shares
        if owned_shares[0]['shares'] < int(shares):
            return apology("Error: You only have {} shares".format(shares))

        # Can proceed to sell
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash[0]['cash'] + sell_amount, user_id)

        # also record the transaction of sold
        db.execute("INSERT INTO transactions(user_id, symbol, type, shares, price) VALUES(?, ?, ?, ?, ?)",
                   user_id, symbol.upper(), "sold", int(shares), current_price["price"])

        # Flash the message
        flash_message = "Sold {} shares of {} for {} money".format(
            shares, symbol.upper(), usd(sell_amount))
        flash(flash_message)

        # redirect to homepage
        return redirect("/")

    # dictionary containing symbols and shares
    symbol_n_shares = db.execute(
        "SELECT symbol, SUM(shares) AS shares FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
    return render_template("sell_shares.html", symbol_n_shares=symbol_n_shares)


@app.route("/change_password", methods=['GET', 'POST'])
def change_password():
    user_id = session["user_id"]
    if request.method == "POST":
        prev_password = request.form.get("prev_password")
        new_password = request.form.get("new_password")
        confirm_new_password = request.form.get("confirm_new_password")

        user_info = db.execute("SELECT hash FROM users WHERE id = ?", user_id)

        # password validation
        prev_password_hash = generate_password_hash(prev_password)
        correct_prev_password_hash = user_info[0]["hash"]

        if not prev_password or not new_password or not confirm_new_password:
            return apology("Error: some fields are not field")

        if not check_password_hash(user_info[0]["hash"], prev_password):
            return apology("Error: previous password was incorrect")

        if new_password != confirm_new_password:
            return apology("Error: new password and confirm new password are different")

        # password can be changed
        new_password_hash = generate_password_hash(new_password)
        db.execute("UPDATE users SET hash = ? WHERE id = ?", new_password_hash, user_id)

        flash("password changed successfully.")
        return redirect("/login")

    return render_template("change_password.html")


@app.route("/cash_deposit", methods=["GET", "POST"])
@login_required
def cash_deposit():
    if request.method == "GET":
        return render_template("cash deposit.html")

    user_id = session["user_id"]
    monthly_deposit_limit = 10000
    deposit_amt = int(request.form.get("amount"))
    print("deposit_amt {}".format(deposit_amt))

    # Calculating the date of first day of current month
    now = datetime.now()
    first_day_of_month = datetime(now.year, now.month, 1)

    # Calculate the total deposits during this month
    result = db.execute("SELECT SUM(price) AS total_deposit FROM transactions WHERE user_id=? AND type=? AND timestamp>=?",
                        user_id, "cash_deposit", first_day_of_month)
    current_total_deposit = result[0]["total_deposit"] or 0
    print("current_total_deposit {}".format(current_total_deposit))

    # Check whether deposit amt will exceed month deposit limit (i.e 10,000)
    if (current_total_deposit + deposit_amt) > monthly_deposit_limit:
        remaining = int(monthly_deposit_limit - current_total_deposit)
        print("remaining {}".format(remaining))
        return apology(f"Monthly deposit limit exceded. You can deposit {remaining:.2f} in this month")

    # update the database for users(cash) transactions-> record
    db.execute("UPDATE users SET cash=cash+? WHERE id=? ", deposit_amt, user_id)
    db.execute("INSERT INTO transactions(user_id, symbol, shares, price, type) VALUES(?,?,?,?,?)",
               user_id, "CASH", "0", deposit_amt, "cash_deposit")

    flash("Deposited {} successfully".format(usd(deposit_amt)))
    return redirect("/")


@app.route("/withdraw_cash", methods=["GET", "POST"])
@login_required
def withdraw_cash():
    if request.method == "GET":
        # Simply show the withdrawal form page
        destination = {'Bank': ['Gemini society development bank', 'Google fun bank', 'Sundharaa Agriculture baink'],
                       'E-wallet': ['nepal_SBI', 'e-sewa', 'khalti'],
                       'Crypto': ['GOOD', 'BAD', 'UGLY'],
                       'Donate': ['Buy me a coffe', 'Pateron', 'GoFundMe', 'SBSK family', 'Bayyinah gift']}

        return render_template("withdraw_cash.html", destination=destination)

    # If method is POST (User clicked "Withdraw")
    user_id = session["user_id"]

    # 1. Grab values from the incoming FORM data
    name = request.form.get("name")
    sub_name = request.form.get("sub_name")
    id_number = request.form.get("id_number")

    try:
        amount = float(request.form.get("amount"))
    except (TypeError, ValueError):
        return apology("Invalid withdrawal amount")

    # 2. Basic Validation
    if not name or not sub_name or not id_number:
        return apology("Please fill out all destination fields")

    if amount <= 0:
        return apology("Withdrawal amount must be greater than zero")

    # 3. Check User's Available Balance Safely
    rows = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    user_cash = rows[0]["cash"]

    if amount > user_cash:
        return apology(f"Insufficient funds. You only have {usd(user_cash)} available.")

    # 4. Process the Withdrawal
    # Deduct from user account balance
    db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", amount, user_id)

    # Record the destination details in the 'symbol' column for tracking
    destination_string = f"{name.upper()} | {sub_name.upper()}"

    db.execute("""
        INSERT INTO transactions (user_id, symbol, shares, price, type)
        VALUES (?, ?, ?, ?, ?)
    """, user_id, destination_string, 0, amount, "cash_withdraw")

    # 5. Success Message and Redirect
    flash(f"Successfully withdrew {usd(amount)} to {sub_name} (ID: {id_number}) !")
    return redirect("/")


# parsing districts of nepal provided in .txt file in a dictionary
# Locate files safely
base_dir = os.path.dirname(__file__)
file_path = os.path.join(base_dir, "static", "nepal_districts")

province_map = {}
current_province = None

# open the file and let the magic happen
with open(file_path, "r") as file:
    for line in file:
        # for removing empty lines and white space
        line = line.strip()

        if not line:
            continue

        # Check if line is province name (starts with *)
        if line.startswith("*"):
            current_province = line.lstrip("*")

            # initialize an empty list for the current_province
            province_map[current_province] = []

        else:
            # If we have a current province add districts to it
            if current_province:
                province_map[current_province].append(line)
