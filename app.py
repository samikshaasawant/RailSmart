from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify
)
from google import genai
from dotenv import load_dotenv
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from models.db_setup import db, User, Station, Train, Booking, Fare
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from urllib.parse import urlparse, urljoin
import os
import time

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "FLASK_SECRET_KEY", "railsmart-local-development-key"
)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///railway.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Gemini configuration.
# The website and login can still start if the API key is missing.
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

# --------------------------------------------------
# LOGIN MANAGER
# --------------------------------------------------

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "error"


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None


def safe_next_url(target):
    """Prevent redirects to external websites."""
    if not target:
        return None

    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))

    if (
        redirect_url.scheme in ("http", "https")
        and host_url.netloc == redirect_url.netloc
    ):
        return target

    return None


# --------------------------------------------------
# SAMPLE DATA
# --------------------------------------------------

def add_sample_data():
    """Add sample stations, trains and a demo account."""

    stations_data = [
        {"name": "Mumbai Central", "code": "BCT"},
        {"name": "New Delhi", "code": "NDLS"},
        {"name": "Chennai Central", "code": "MAS"},
        {"name": "Kolkata Howrah", "code": "HWH"},
        {"name": "Bangalore City", "code": "SBC"},
        {"name": "Hyderabad Deccan", "code": "HYB"},
        {"name": "Pune Junction", "code": "PUNE"},
        {"name": "Jaipur Junction", "code": "JP"},
        {"name": "Lucknow", "code": "LKO"},
    ]

    # Add only stations that do not already exist.
    for item in stations_data:
        if not Station.query.filter_by(code=item["code"]).first():
            db.session.add(
                Station(name=item["name"], code=item["code"])
            )

    db.session.commit()

    stations = {
        station.code: station
        for station in Station.query.all()
    }

    trains_data = [
        ("Rajdhani Express", "12951", "BCT", "NDLS",
         "16:00", "08:30", 120),
        ("Mumbai Rajdhani", "12953", "BCT", "NDLS",
         "17:30", "10:15", 100),
        ("August Kranti", "12933", "BCT", "NDLS",
         "17:05", "09:30", 80),
        ("Mumbai Duronto", "12201", "NDLS", "BCT",
         "22:20", "11:00", 110),
        ("Chennai Express", "11041", "BCT", "MAS",
         "11:10", "14:00", 90),
        ("Tamil Nadu Express", "12621", "NDLS", "MAS",
         "22:30", "06:45", 100),
        ("Udyan Express", "11301", "BCT", "SBC",
         "21:05", "12:30", 85),
        ("Sampark Kranti", "12649", "NDLS", "SBC",
         "11:50", "15:30", 95),
        ("Poorva Express", "12303", "HWH", "NDLS",
         "14:50", "09:25", 110),
        ("Shatabdi Express", "12007", "SBC", "MAS",
         "06:00", "11:00", 75),
        ("Charminar Express", "12759", "HYB", "SBC",
         "20:45", "06:15", 80),
        ("Deccan Queen", "12123", "PUNE", "BCT",
         "17:10", "20:25", 70),
        ("Jaipur Shatabdi", "12015", "JP", "NDLS",
         "17:40", "22:35", 65),
        ("Lucknow Mail", "12229", "LKO", "NDLS",
         "22:15", "07:00", 90),
    ]

    for item in trains_data:
        name, number, source, dest, departure, arrival, seats = item

        # Avoid duplicating existing trains.
        if Train.query.filter_by(train_number=number).first():
            continue

        source_station = stations.get(source)
        destination_station = stations.get(dest)

        if not source_station or not destination_station:
            continue

        train = Train(
            train_name=name,
            train_number=number,
            source_id=source_station.station_id,
            destination_id=destination_station.station_id,
            departure_time=departure,
            arrival_time=arrival,
            total_seats=seats,
            available_seats=seats,
        )

        db.session.add(train)

    # Demo account
    if not User.query.filter_by(
        email="demo@example.com"
    ).first():
        db.session.add(
            User(
                name="Demo User",
                email="demo@example.com",
                password=generate_password_hash("password123"),
            )
        )

    db.session.commit()


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def index():
    stations = Station.query.all()
    today = date.today().isoformat()

    return render_template(
        "index.html",
        stations=stations,
        today=today
    )


# --------------------------------------------------
# SEARCH TRAINS
# --------------------------------------------------

@app.route("/search", methods=["GET", "POST"])
def search_trains():
    if request.method != "POST":
        return redirect(url_for("index"))

    source_id = request.form.get("source")
    destination_id = request.form.get("destination")
    journey_date = request.form.get("journey_date")

    if not source_id or not destination_id:
        flash("Please select both source and destination stations!", "error")
        return redirect(url_for("index"))

    try:
        source_id = int(source_id)
        destination_id = int(destination_id)
    except (ValueError, TypeError):
        flash("Please select valid stations.", "error")
        return redirect(url_for("index"))

    if source_id == destination_id:
        flash("Source and destination cannot be the same!", "error")
        return redirect(url_for("index"))

    trains = Train.query.filter_by(
        source_id=source_id,
        destination_id=destination_id
    ).all()

    stations = Station.query.all()

    return render_template(
        "search.html",
        trains=trains,
        stations=stations,
        journey_date=journey_date
    )


# --------------------------------------------------
# BOOK TRAIN
# --------------------------------------------------

@app.route("/book/<int:train_id>", methods=["GET", "POST"])
@login_required
def book_train(train_id):
    train = Train.query.get_or_404(train_id)

    if request.method == "POST":
        try:
            seats = int(request.form.get("seats", 1))
        except (ValueError, TypeError):
            flash("Please select a valid number of seats.", "error")
            return redirect(url_for("book_train", train_id=train_id))

        journey_date = request.form.get("journey_date")

        if not journey_date:
            flash("Please select journey date!", "error")
            return redirect(url_for("book_train", train_id=train_id))

        try:
            parsed_date = datetime.strptime(
                journey_date, "%Y-%m-%d"
            ).date()
        except ValueError:
            flash("Please select a valid journey date.", "error")
            return redirect(url_for("book_train", train_id=train_id))

        if parsed_date < date.today():
            flash("Journey date cannot be in the past.", "error")
            return redirect(url_for("book_train", train_id=train_id))

        if seats <= 0:
            flash("Please select at least 1 seat!", "error")
            return redirect(url_for("book_train", train_id=train_id))

        if seats > train.available_seats:
            flash(
                f"Only {train.available_seats} seats available!",
                "error"
            )
            return redirect(url_for("book_train", train_id=train_id))

        route_distances = {
            ("BCT", "NDLS"): 1384,
            ("NDLS", "BCT"): 1384,
            ("BCT", "MAS"): 1288,
            ("NDLS", "MAS"): 2180,
            ("BCT", "SBC"): 984,
            ("NDLS", "SBC"): 2150,
            ("HWH", "NDLS"): 1453,
            ("SBC", "MAS"): 362,
            ("HYB", "SBC"): 569,
            ("PUNE", "BCT"): 192,
            ("JP", "NDLS"): 304,
            ("LKO", "NDLS"): 512,
        }

        distance = route_distances.get(
            (train.source.code, train.destination.code), 500
        )

        total_amount = seats * distance * 2

        booking = Booking(
            user_id=current_user.user_id,
            train_id=train_id,
            seats_booked=seats,
            booking_date=datetime.now().date(),
            journey_date=parsed_date,
            total_amount=total_amount,
            status="Confirmed",
        )

        train.available_seats -= seats
        db.session.add(booking)
        db.session.commit()

        flash(
            f"Booking confirmed! Booking ID: {booking.booking_id}",
            "success"
        )

        return redirect(url_for("my_bookings"))

    return render_template("book.html", train=train)


# --------------------------------------------------
# MY BOOKINGS
# --------------------------------------------------

@app.route("/mybookings")
@login_required
def my_bookings():
    bookings = Booking.query.filter_by(
        user_id=current_user.user_id
    ).order_by(Booking.booking_date.desc()).all()

    return render_template(
        "mybookings.html",
        bookings=bookings
    )


# --------------------------------------------------
# CANCEL BOOKING
# --------------------------------------------------

@app.route("/cancel/<int:booking_id>", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    if booking.user_id != current_user.user_id:
        flash("Unauthorized action!", "error")
        return redirect(url_for("my_bookings"))

    if booking.status == "Cancelled":
        flash("Booking already cancelled!", "warning")
        return redirect(url_for("my_bookings"))

    train = Train.query.get(booking.train_id)

    if train:
        train.available_seats = min(
            train.total_seats,
            train.available_seats + booking.seats_booked
        )

    booking.status = "Cancelled"
    db.session.commit()

    flash("Booking cancelled successfully!", "success")
    return redirect(url_for("my_bookings"))


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Please enter your email and password.", "error")
            return render_template("login.html")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)

            flash("Logged in successfully!", "success")

            next_page = safe_next_url(request.args.get("next"))

            return redirect(
                next_page or url_for("index")
            )

        flash("Invalid email or password!", "error")

    return render_template("login.html")


# --------------------------------------------------
# REGISTER
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not name or not email or not password:
            flash("Please fill in all required fields.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "error")
            return render_template("register.html")

        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
        )

        db.session.add(user)
        db.session.commit()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    flash("Logged out successfully!", "success")
    return redirect(url_for("index"))


# --------------------------------------------------
# ALL TRAINS
# --------------------------------------------------

@app.route("/all-trains")
def all_trains():
    trains = Train.query.all()

    return render_template(
        "all_trains.html",
        trains=trains
    )


# --------------------------------------------------
# GEMINI CHATBOT
# --------------------------------------------------

@app.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({
            "reply": "Please enter a message."
        }), 400

    if client is None:
        app.logger.error("GEMINI_API_KEY is missing.")
        return jsonify({
            "reply": (
                "The AI assistant is not configured yet. "
                "Please add GEMINI_API_KEY to your .env file."
            )
        }), 503

    # Keep the prompt focused on the RailSmart website.
    prompt = f"""
You are RailSmart's helpful railway assistant.

Help users understand how to use RailSmart, search trains,
understand sample fares, and manage bookings.

Important:
- This is a college project.
- Do not claim to have real-time railway availability.
- Do not claim to know live train status.
- Do not claim to have access to a user's private bookings.
- Explain that displayed train and fare information is sample
  project data and may not represent official railway information.
- Keep replies friendly, clear, and concise.

User message:
{message}
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt
        )

        reply = getattr(response, "text", None)

        if not reply:
            reply = "Sorry, I couldn't generate a reply. Please try again."

        return jsonify({"reply": reply})

    except Exception:
        app.logger.exception("Gemini chatbot request failed.")

        return jsonify({
            "reply": (
                "Sorry, the AI assistant is temporarily unavailable. "
                "Please check your API key and connection, then try again."
            )
        }), 502


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

with app.app_context():
    db.create_all()
    add_sample_data()


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)