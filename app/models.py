from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import enum
import math

db = SQLAlchemy()

TRIAL_DAYS = 7


class TierEnum(enum.Enum):
    # FREE = "not paying" (in trial, expired, or canceled). PRO = paying subscriber.
    # The Free tier as a permanent state is gone — access is gated by trial_ends_at.
    FREE = "Free"
    PRO = "Pro"


def _ensure_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


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
    trial_ends_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_pro(self):
        return self.tier == TierEnum.PRO

    @property
    def is_in_trial(self):
        ends = _ensure_aware(self.trial_ends_at)
        return ends is not None and ends > datetime.now(timezone.utc)

    @property
    def trial_expired(self):
        ends = _ensure_aware(self.trial_ends_at)
        return ends is not None and ends <= datetime.now(timezone.utc)

    @property
    def has_access(self):
        return self.is_pro or self.is_in_trial

    @property
    def trial_days_remaining(self):
        ends = _ensure_aware(self.trial_ends_at)
        if ends is None:
            return 0
        delta = ends - datetime.now(timezone.utc)
        if delta.total_seconds() <= 0:
            return 0
        return max(1, math.ceil(delta.total_seconds() / 86400))

    def start_trial(self, days=TRIAL_DAYS):
        self.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=days)

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


class AgentToken(db.Model):
    __tablename__ = "agent_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    scopes = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime)


class WorkSession(db.Model):
    __tablename__ = "work_sessions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False)
    finished_at = db.Column(db.DateTime)
    budget_seconds = db.Column(db.Integer, nullable=False)
    approved_at = db.Column(db.DateTime)
    spans = db.relationship("WorkSpan", backref="work", lazy=True, cascade="all, delete-orphan")
    events = db.relationship("WorkEvent", backref="work", lazy=True, cascade="all, delete-orphan")


class WorkSpan(db.Model):
    __tablename__ = "work_spans"
    id = db.Column(db.Integer, primary_key=True)
    work_id = db.Column(db.Integer, db.ForeignKey("work_sessions.id"), nullable=False, index=True)
    actor_id = db.Column(db.String(100), nullable=False)
    actor_kind = db.Column(db.String(10), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False)
    ended_at = db.Column(db.DateTime)
    lease_until = db.Column(db.DateTime)
    stop_reason = db.Column(db.String(30))


class WorkEvent(db.Model):
    __tablename__ = "work_events"
    id = db.Column(db.Integer, primary_key=True)
    work_id = db.Column(db.Integer, db.ForeignKey("work_sessions.id"), nullable=False, index=True)
    at = db.Column(db.DateTime, nullable=False)
    kind = db.Column(db.String(30), nullable=False)
    actor_id = db.Column(db.String(100))
    source = db.Column(db.String(100), nullable=False)
    data = db.Column(db.JSON, nullable=False)


class WorkOperation(db.Model):
    """Persist responses so retries cannot duplicate work."""
    __tablename__ = "work_operations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    request_id = db.Column(db.String(100), nullable=False)
    fingerprint = db.Column(db.String(64), nullable=False)
    response = db.Column(db.JSON, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "request_id"),)


class WorkDraft(db.Model):
    __tablename__ = "work_drafts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False)
    approved_at = db.Column(db.DateTime)
    data = db.Column(db.JSON, nullable=False)
    approval = db.Column(db.JSON)
