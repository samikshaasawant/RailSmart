from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    
    def get_id(self):
        return str(self.user_id)

class Station(db.Model):
    __tablename__ = 'stations'
    station_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)

class Train(db.Model):
    __tablename__ = 'trains'
    train_id = db.Column(db.Integer, primary_key=True)
    train_name = db.Column(db.String(100), nullable=False)
    train_number = db.Column(db.String(20), unique=True, nullable=False)
    source_id = db.Column(db.Integer, db.ForeignKey('stations.station_id'), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey('stations.station_id'), nullable=False)
    departure_time = db.Column(db.String(8), nullable=False)
    arrival_time = db.Column(db.String(8), nullable=False)
    total_seats = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    
    source = db.relationship('Station', foreign_keys=[source_id])
    destination = db.relationship('Station', foreign_keys=[destination_id])

class Booking(db.Model):
    __tablename__ = 'bookings'
    booking_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    train_id = db.Column(db.Integer, db.ForeignKey('trains.train_id'), nullable=False)
    seats_booked = db.Column(db.Integer, nullable=False)
    booking_date = db.Column(db.Date, nullable=False)
    journey_date = db.Column(db.Date, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Confirmed')
    
    user = db.relationship('User')
    train = db.relationship('Train')

class Fare(db.Model):
    __tablename__ = 'fares'
    fare_id = db.Column(db.Integer, primary_key=True)
    train_id = db.Column(db.Integer, db.ForeignKey('trains.train_id'), nullable=False)
    class_type = db.Column(db.String(50), nullable=False)
    fare_per_seat = db.Column(db.Float, nullable=False)
    
    train = db.relationship('Train')