from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
import enum

db = SQLAlchemy()


class TierEnum(enum.Enum):
    FREE = "Free"
    PRO = "Pro"


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    tier = db.Column(db.Enum(TierEnum), nullable=False, default=TierEnum.FREE)
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)
    upgraded_at = db.Column(db.DateTime, nullable=True)
    trial_started_at = db.Column(db.DateTime, nullable=True)
    banner_dismissed = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_pro(self):
        """Check if user has an active Pro subscription"""
        return self.tier == TierEnum.PRO

    @property
    def trial_end_date(self):
        """Calculate when the trial ends (14 days from start)"""
        if not self.trial_started_at:
            return None
        return self.trial_started_at + timedelta(days=14)

    @property
    def trial_days_remaining(self):
        """Calculate how many days remain in the trial"""
        if not self.trial_started_at or self.is_pro:
            return None

        end_date = self.trial_end_date
        now = datetime.now(timezone.utc)

        if now >= end_date:
            return 0

        days_left = (end_date - now).days
        return days_left

    @property
    def is_trial_active(self):
        """Check if the free trial is still active"""
        if self.is_pro:
            return False

        if not self.trial_started_at:
            return False

        return datetime.now(timezone.utc) < self.trial_end_date

    @property
    def has_access(self):
        """Check if user has access to the app (trial active OR pro subscription)"""
        return self.is_pro or self.is_trial_active

    def __repr__(self):
        return f'<User {self.email}>'


class Client(db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    hourly_rate = db.Column(db.Float, nullable=False, default=0.0)

    user = db.relationship('User', backref=db.backref('clients', lazy=True), foreign_keys=[user_id])

    def get_running_timer(self):
        """Get the current running timer for this client, if any"""
        return TimeEntry.query.filter_by(
            client_id=self.id,
            user_id=self.user_id,
            end_time=None
        ).first()

    def __repr__(self):
        return f'<Client {self.name}>'


class TimeEntry(db.Model):
    __tablename__ = 'time_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    notes = db.Column(db.Text)

    user = db.relationship('User', backref=db.backref('time_entries', lazy=True), foreign_keys=[user_id])
    client = db.relationship('Client', backref=db.backref('time_entries', lazy=True), foreign_keys=[client_id])

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
        return f'<TimeEntry {self.id}>'


class Timesheet(db.Model):
    __tablename__ = 'timesheets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)
    total_hours = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    csv_data = db.Column(db.Text, nullable=False)  # Store CSV content as text
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('timesheets', lazy=True), foreign_keys=[user_id])
    client = db.relationship('Client', backref=db.backref('timesheets', lazy=True), foreign_keys=[client_id])

    def __repr__(self):
        return f'<Timesheet {self.id} - {self.client.name if self.client else "No Client"} {self.month}/{self.year}>'