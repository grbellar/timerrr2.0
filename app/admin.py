import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from app.models import Client, TierEnum, TimeEntry, Timesheet, User, db

admin = Blueprint("admin", __name__, url_prefix="/admin")


DEFAULT_ADMIN_EMAILS = {"ayokayitsfine@gmail.com"}


def _admin_emails():
    raw = os.environ.get("ADMIN_EMAILS", "")
    extra = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return DEFAULT_ADMIN_EMAILS | extra


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(404)
        if (current_user.email or "").lower() not in _admin_emails():
            abort(404)
        return view(*args, **kwargs)

    return wrapped


def _utcnow():
    return datetime.now(timezone.utc)


def _entry_seconds_expr():
    """SQL expression for completed entry duration in seconds (SQLite-friendly)."""
    return func.coalesce(
        func.sum(
            (func.julianday(TimeEntry.end_time) - func.julianday(TimeEntry.start_time))
            * 86400.0
        ),
        0.0,
    )


@admin.route("/")
@admin_required
def overview():
    now = _utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    total_users = db.session.query(func.count(User.id)).scalar() or 0
    pro_users = (
        db.session.query(func.count(User.id))
        .filter(User.tier == TierEnum.PRO)
        .scalar()
        or 0
    )
    free_users = total_users - pro_users
    paying_users = (
        db.session.query(func.count(User.id))
        .filter(User.stripe_subscription_id.isnot(None))
        .scalar()
        or 0
    )

    signups_24h = (
        db.session.query(func.count(User.id))
        .filter(User.created_at >= last_24h)
        .scalar()
        or 0
    )
    signups_7d = (
        db.session.query(func.count(User.id))
        .filter(User.created_at >= last_7d)
        .scalar()
        or 0
    )
    signups_30d = (
        db.session.query(func.count(User.id))
        .filter(User.created_at >= last_30d)
        .scalar()
        or 0
    )

    total_clients = db.session.query(func.count(Client.id)).scalar() or 0
    total_entries = db.session.query(func.count(TimeEntry.id)).scalar() or 0
    total_timesheets = db.session.query(func.count(Timesheet.id)).scalar() or 0

    total_seconds = (
        db.session.query(_entry_seconds_expr())
        .filter(TimeEntry.end_time.isnot(None))
        .scalar()
        or 0.0
    )
    total_hours = total_seconds / 3600.0

    running_timers = (
        db.session.query(func.count(TimeEntry.id))
        .filter(TimeEntry.end_time.is_(None))
        .scalar()
        or 0
    )

    entries_24h = (
        db.session.query(func.count(TimeEntry.id))
        .filter(TimeEntry.start_time >= last_24h)
        .scalar()
        or 0
    )
    entries_7d = (
        db.session.query(func.count(TimeEntry.id))
        .filter(TimeEntry.start_time >= last_7d)
        .scalar()
        or 0
    )

    active_users_7d = (
        db.session.query(func.count(func.distinct(TimeEntry.user_id)))
        .filter(TimeEntry.start_time >= last_7d)
        .scalar()
        or 0
    )
    active_users_30d = (
        db.session.query(func.count(func.distinct(TimeEntry.user_id)))
        .filter(TimeEntry.start_time >= last_30d)
        .scalar()
        or 0
    )

    recent_signups = (
        User.query.order_by(User.created_at.desc()).limit(8).all()
    )

    running_timer_rows = (
        db.session.query(TimeEntry, User, Client)
        .join(User, User.id == TimeEntry.user_id)
        .outerjoin(Client, Client.id == TimeEntry.client_id)
        .filter(TimeEntry.end_time.is_(None))
        .order_by(TimeEntry.start_time.desc())
        .limit(20)
        .all()
    )

    daily_signups = []
    for i in range(13, -1, -1):
        day_start = (now - timedelta(days=i)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end = day_start + timedelta(days=1)
        count = (
            db.session.query(func.count(User.id))
            .filter(User.created_at >= day_start, User.created_at < day_end)
            .scalar()
            or 0
        )
        daily_signups.append({"date": day_start, "count": count})
    max_daily = max((d["count"] for d in daily_signups), default=0)

    top_users_by_hours = (
        db.session.query(
            User,
            _entry_seconds_expr().label("seconds"),
            func.count(TimeEntry.id).label("entries"),
        )
        .join(TimeEntry, TimeEntry.user_id == User.id)
        .filter(TimeEntry.end_time.isnot(None))
        .group_by(User.id)
        .order_by(_entry_seconds_expr().desc())
        .limit(10)
        .all()
    )

    return render_template(
        "admin/overview.html",
        total_users=total_users,
        pro_users=pro_users,
        free_users=free_users,
        paying_users=paying_users,
        signups_24h=signups_24h,
        signups_7d=signups_7d,
        signups_30d=signups_30d,
        total_clients=total_clients,
        total_entries=total_entries,
        total_timesheets=total_timesheets,
        total_hours=total_hours,
        running_timers=running_timers,
        entries_24h=entries_24h,
        entries_7d=entries_7d,
        active_users_7d=active_users_7d,
        active_users_30d=active_users_30d,
        recent_signups=recent_signups,
        running_timer_rows=running_timer_rows,
        daily_signups=daily_signups,
        max_daily=max_daily,
        top_users_by_hours=top_users_by_hours,
        now=now,
    )


@admin.route("/users")
@admin_required
def users_list():
    q = (request.args.get("q") or "").strip()
    sort = request.args.get("sort", "recent")

    clients_sq = (
        db.session.query(
            Client.user_id.label("uid"),
            func.count(Client.id).label("clients_count"),
        )
        .group_by(Client.user_id)
        .subquery()
    )

    entries_sq = (
        db.session.query(
            TimeEntry.user_id.label("uid"),
            func.count(TimeEntry.id).label("entries_count"),
            func.coalesce(
                func.sum(
                    (
                        func.julianday(TimeEntry.end_time)
                        - func.julianday(TimeEntry.start_time)
                    )
                    * 86400.0
                ),
                0.0,
            ).label("seconds"),
            func.max(TimeEntry.start_time).label("last_activity"),
        )
        .filter(TimeEntry.end_time.isnot(None))
        .group_by(TimeEntry.user_id)
        .subquery()
    )

    last_any_sq = (
        db.session.query(
            TimeEntry.user_id.label("uid"),
            func.max(TimeEntry.start_time).label("last_any"),
        )
        .group_by(TimeEntry.user_id)
        .subquery()
    )

    query = (
        db.session.query(
            User,
            func.coalesce(clients_sq.c.clients_count, 0).label("clients_count"),
            func.coalesce(entries_sq.c.entries_count, 0).label("entries_count"),
            func.coalesce(entries_sq.c.seconds, 0.0).label("seconds"),
            last_any_sq.c.last_any.label("last_activity"),
        )
        .outerjoin(clients_sq, clients_sq.c.uid == User.id)
        .outerjoin(entries_sq, entries_sq.c.uid == User.id)
        .outerjoin(last_any_sq, last_any_sq.c.uid == User.id)
    )

    if q:
        query = query.filter(User.email.ilike(f"%{q}%"))

    if sort == "hours":
        query = query.order_by(func.coalesce(entries_sq.c.seconds, 0.0).desc())
    elif sort == "entries":
        query = query.order_by(func.coalesce(entries_sq.c.entries_count, 0).desc())
    elif sort == "active":
        query = query.order_by(last_any_sq.c.last_any.desc().nullslast())
    elif sort == "tier":
        query = query.order_by(User.tier.desc(), User.created_at.desc())
    else:
        query = query.order_by(User.created_at.desc())

    rows = query.limit(500).all()

    return render_template(
        "admin/users.html",
        rows=rows,
        q=q,
        sort=sort,
    )


@admin.route("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)

    clients_with_stats = (
        db.session.query(
            Client,
            func.count(TimeEntry.id).label("entries"),
            _entry_seconds_expr().label("seconds"),
        )
        .outerjoin(
            TimeEntry,
            (TimeEntry.client_id == Client.id) & (TimeEntry.end_time.isnot(None)),
        )
        .filter(Client.user_id == user.id)
        .group_by(Client.id)
        .order_by(Client.created_at.desc())
        .all()
    )

    recent_entries = (
        db.session.query(TimeEntry, Client)
        .outerjoin(Client, Client.id == TimeEntry.client_id)
        .filter(TimeEntry.user_id == user.id)
        .order_by(TimeEntry.start_time.desc())
        .limit(50)
        .all()
    )

    timesheets = (
        db.session.query(Timesheet, Client)
        .outerjoin(Client, Client.id == Timesheet.client_id)
        .filter(Timesheet.user_id == user.id)
        .order_by(Timesheet.created_at.desc())
        .limit(50)
        .all()
    )

    total_entries = (
        db.session.query(func.count(TimeEntry.id))
        .filter(TimeEntry.user_id == user.id)
        .scalar()
        or 0
    )
    total_seconds = (
        db.session.query(_entry_seconds_expr())
        .filter(TimeEntry.user_id == user.id, TimeEntry.end_time.isnot(None))
        .scalar()
        or 0.0
    )
    running = (
        db.session.query(TimeEntry, Client)
        .outerjoin(Client, Client.id == TimeEntry.client_id)
        .filter(TimeEntry.user_id == user.id, TimeEntry.end_time.is_(None))
        .first()
    )
    last_activity = (
        db.session.query(func.max(TimeEntry.start_time))
        .filter(TimeEntry.user_id == user.id)
        .scalar()
    )

    return render_template(
        "admin/user_detail.html",
        user=user,
        clients_with_stats=clients_with_stats,
        recent_entries=recent_entries,
        timesheets=timesheets,
        total_entries=total_entries,
        total_hours=(total_seconds or 0) / 3600.0,
        running=running,
        last_activity=last_activity,
        now=_utcnow(),
    )
