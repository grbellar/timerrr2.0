from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import enum

db = SQLAlchemy()


class TierEnum(enum.Enum):
    FREE = "Free"
    PRO = "Pro"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    tier = db.Column(db.Enum(TierEnum), nullable=False, default=TierEnum.FREE)
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)
    upgraded_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"


class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    hourly_rate = db.Column(db.Float, nullable=False, default=0.0)

    user = db.relationship(
        "User", backref=db.backref("clients", lazy=True), foreign_keys=[user_id]
    )

    def get_running_timer(self):
        """Get the current running timer for this client, if any"""
        return TimeEntry.query.filter_by(
            client_id=self.id, user_id=self.user_id, end_time=None
        ).first()

    def __repr__(self):
        return f"<Client {self.name}>"


class TimeEntry(db.Model):
    __tablename__ = "time_entries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    notes = db.Column(db.Text)

    user = db.relationship(
        "User", backref=db.backref("time_entries", lazy=True), foreign_keys=[user_id]
    )
    client = db.relationship(
        "Client",
        backref=db.backref("time_entries", lazy=True),
        foreign_keys=[client_id],
    )

    @property
    def duration(self):
        if self.end_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds()
        return None

    @property
    def is_running(self):
        return self.end_time is None

    def __repr__(self):
        return f"<TimeEntry {self.id}>"


class Timesheet(db.Model):
    __tablename__ = "timesheets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)
    period_start_utc = db.Column(db.DateTime, nullable=True)
    period_end_utc = db.Column(db.DateTime, nullable=True)
    period_timezone = db.Column(db.String(64), nullable=True)
    period_type = db.Column(db.String(20), nullable=True)  # "monthly" | "range"
    total_hours = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    csv_data = db.Column(db.Text, nullable=False)  # Store CSV content as text
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship(
        "User", backref=db.backref("timesheets", lazy=True), foreign_keys=[user_id]
    )
    client = db.relationship(
        "Client", backref=db.backref("timesheets", lazy=True), foreign_keys=[client_id]
    )

    def __repr__(self):
        return f"<Timesheet {self.id} - {self.client.name if self.client else 'No Client'} {self.month}/{self.year}>"
