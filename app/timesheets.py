from datetime import date, datetime, time, timedelta, timezone
import calendar
import csv
import io
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import and_

from app.models import Client, TimeEntry, Timesheet, db

timesheets = Blueprint("timesheets", __name__)


def _ensure_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_client_filename(name):
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name).strip("_")
    return safe or "client"


def _client_name(timesheet):
    return timesheet.client.name if timesheet.client else "Deleted Client"


def _format_hms(total_seconds):
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _parse_range_request(data):
    if not data:
        raise ValueError("Missing required fields")

    client_id = data.get("client_id")
    start_date_raw = data.get("start_date")
    end_date_raw = data.get("end_date")
    timezone_name = (data.get("timezone") or "UTC").strip() or "UTC"

    if not all([client_id, start_date_raw, end_date_raw]):
        raise ValueError("Missing required fields")

    try:
        client_id = int(client_id)
        start_date = date.fromisoformat(start_date_raw)
        end_date = date.fromisoformat(end_date_raw)
    except (TypeError, ValueError):
        raise ValueError("Invalid data format")

    if end_date < start_date:
        raise ValueError("End date must be on or after start date")

    total_days = (end_date - start_date).days + 1
    if total_days > 366:
        raise ValueError("Range cannot exceed 366 days")

    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise ValueError("Invalid timezone")

    period_start_local = datetime.combine(start_date, time.min, tzinfo=tz)
    period_end_local_exclusive = datetime.combine(
        end_date + timedelta(days=1), time.min, tzinfo=tz
    )

    return {
        "client_id": client_id,
        "start_date": start_date,
        "end_date": end_date,
        "timezone_name": timezone_name,
        "timezone": tz,
        "period_start_utc": period_start_local.astimezone(timezone.utc),
        "period_end_utc": period_end_local_exclusive.astimezone(timezone.utc),
    }


def _serialize_timesheet(timesheet):
    payload = {
        "id": timesheet.id,
        "client_id": timesheet.client_id,
        "client_name": _client_name(timesheet),
        "total_hours": round(timesheet.total_hours, 4),
        "total_amount": round(timesheet.total_amount, 2),
        "created_at": _ensure_utc(timesheet.created_at).isoformat().replace("+00:00", "Z"),
    }

    if (
        timesheet.period_type == "range"
        and timesheet.period_start_utc
        and timesheet.period_end_utc
    ):
        timezone_name = timesheet.period_timezone or "UTC"
        try:
            tz = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            timezone_name = "UTC"
            tz = timezone.utc

        period_start_local = _ensure_utc(timesheet.period_start_utc).astimezone(tz).date()
        period_end_local = (
            _ensure_utc(timesheet.period_end_utc) - timedelta(microseconds=1)
        ).astimezone(tz).date()

        payload.update(
            {
                "period_type": "range",
                "start_date": period_start_local.isoformat(),
                "end_date": period_end_local.isoformat(),
                "timezone": timezone_name,
            }
        )
    else:
        payload.update(
            {
                "period_type": "monthly",
                "month": timesheet.month,
                "year": timesheet.year,
            }
        )

    return payload


@timesheets.route("/api/timesheets/generate-range", methods=["POST"])
@login_required
def generate_timesheet_range():
    """Generate a timesheet for a specific date range."""
    data = request.get_json(silent=True) or {}

    try:
        parsed = _parse_range_request(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    client = Client.query.filter_by(
        id=parsed["client_id"], user_id=current_user.id
    ).first()
    if not client:
        return jsonify({"error": "Client not found"}), 404

    existing = Timesheet.query.filter_by(
        user_id=current_user.id,
        client_id=parsed["client_id"],
        period_type="range",
        period_start_utc=parsed["period_start_utc"],
        period_end_utc=parsed["period_end_utc"],
        period_timezone=parsed["timezone_name"],
    ).first()
    if existing:
        return jsonify({"error": "Timesheet already exists for this period"}), 409

    entries = (
        TimeEntry.query.filter(
            and_(
                TimeEntry.user_id == current_user.id,
                TimeEntry.client_id == parsed["client_id"],
                TimeEntry.end_time.isnot(None),  # Running timers are excluded
                TimeEntry.end_time > parsed["period_start_utc"],
                TimeEntry.start_time < parsed["period_end_utc"],
            )
        )
        .order_by(TimeEntry.start_time)
        .all()
    )

    if not entries:
        return jsonify({"error": "No time entries found for this period"}), 404

    output = io.StringIO()
    writer = csv.writer(output)

    generated_at = datetime.now(timezone.utc)
    writer.writerow(["Client", client.name])
    writer.writerow(["Period Start", parsed["start_date"].isoformat()])
    writer.writerow(["Period End", parsed["end_date"].isoformat()])
    writer.writerow(["Timezone", parsed["timezone_name"]])
    writer.writerow(
        ["Generated At (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S")]
    )
    writer.writerow([])
    writer.writerow(
        [
            "Date",
            "Start Time",
            "End Time",
            "Duration (HH:MM:SS)",
            "Duration (hrs)",
            "Description",
            "Rate",
            "Amount",
        ]
    )

    total_seconds = 0
    total_amount = 0.0
    hourly_rate = client.hourly_rate or 0.0
    included_entries = 0

    for entry in entries:
        start_utc = _ensure_utc(entry.start_time)
        end_utc = _ensure_utc(entry.end_time)

        effective_start = max(start_utc, parsed["period_start_utc"])
        effective_end = min(end_utc, parsed["period_end_utc"])
        if effective_end <= effective_start:
            continue

        duration_seconds = max(
            0, int((effective_end - effective_start).total_seconds())
        )
        if duration_seconds == 0:
            continue

        included_entries += 1
        total_seconds += duration_seconds

        duration_hours = duration_seconds / 3600
        amount = duration_hours * hourly_rate
        total_amount += amount

        start_local = effective_start.astimezone(parsed["timezone"])
        end_local = effective_end.astimezone(parsed["timezone"])

        writer.writerow(
            [
                start_local.strftime("%Y-%m-%d"),
                start_local.strftime("%H:%M:%S"),
                end_local.strftime("%H:%M:%S"),
                _format_hms(duration_seconds),
                f"{duration_hours:.4f}",
                entry.notes or "",
                f"{hourly_rate:.2f}",
                f"{amount:.2f}",
            ]
        )

    if included_entries == 0:
        return jsonify({"error": "No time entries found for this period"}), 404

    total_hours = total_seconds / 3600
    writer.writerow(
        [
            "",
            "",
            "Total:",
            _format_hms(total_seconds),
            f"{total_hours:.4f}",
            "",
            "",
            f"{total_amount:.2f}",
        ]
    )

    timesheet = Timesheet(
        user_id=current_user.id,
        client_id=parsed["client_id"],
        month=parsed["start_date"].month,
        year=parsed["start_date"].year,
        period_start_utc=parsed["period_start_utc"],
        period_end_utc=parsed["period_end_utc"],
        period_timezone=parsed["timezone_name"],
        period_type="range",
        total_hours=total_hours,
        total_amount=total_amount,
        csv_data=output.getvalue(),
    )
    db.session.add(timesheet)
    db.session.commit()

    return (
        jsonify(
            {
                "id": timesheet.id,
                "client_id": parsed["client_id"],
                "client_name": client.name,
                "period_type": "range",
                "start_date": parsed["start_date"].isoformat(),
                "end_date": parsed["end_date"].isoformat(),
                "timezone": parsed["timezone_name"],
                "entry_count": included_entries,
                "total_hours": round(total_hours, 4),
                "total_amount": round(total_amount, 2),
                "created_at": _ensure_utc(timesheet.created_at)
                .isoformat()
                .replace("+00:00", "Z"),
            }
        ),
        201,
    )


@timesheets.route("/api/timesheets/generate", methods=["POST"])
@login_required
def generate_timesheet():
    """Generate a month-based timesheet (legacy endpoint)."""
    data = request.json or {}

    client_id = data.get("client_id")
    month = data.get("month")
    year = data.get("year")

    if not all([client_id, month, year]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        client_id = int(client_id)
        month = int(month)
        year = int(year)

        if month < 1 or month > 12:
            return jsonify({"error": "Invalid month"}), 400
        if year < 2020 or year > 2030:
            return jsonify({"error": "Invalid year"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid data format"}), 400

    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first()
    if not client:
        return jsonify({"error": "Client not found"}), 404

    existing = Timesheet.query.filter_by(
        user_id=current_user.id, client_id=client_id, month=month, year=year
    ).first()
    if existing:
        return jsonify({"error": "Timesheet already exists for this period"}), 409

    period_start_utc = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        period_end_utc = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        period_end_utc = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    last_day = period_end_utc - timedelta(microseconds=1)

    entries = (
        TimeEntry.query.filter(
            and_(
                TimeEntry.user_id == current_user.id,
                TimeEntry.client_id == client_id,
                TimeEntry.start_time >= period_start_utc,
                TimeEntry.start_time <= last_day,
                TimeEntry.end_time.isnot(None),
            )
        )
        .order_by(TimeEntry.start_time)
        .all()
    )

    if not entries:
        return jsonify({"error": "No time entries found for this period"}), 404

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Date",
            "Start Time",
            "End Time",
            "Duration (HH:MM:SS)",
            "Duration (hrs)",
            "Description",
            "Rate",
            "Amount",
        ]
    )

    total_seconds = 0
    total_amount = 0.0
    hourly_rate = client.hourly_rate or 0.0

    for entry in entries:
        start_time = _ensure_utc(entry.start_time)
        end_time = _ensure_utc(entry.end_time)
        duration_seconds = max(0, int((end_time - start_time).total_seconds()))
        duration_hours = duration_seconds / 3600
        amount = duration_hours * hourly_rate

        total_seconds += duration_seconds
        total_amount += amount

        writer.writerow(
            [
                start_time.strftime("%Y-%m-%d"),
                start_time.strftime("%H:%M:%S"),
                end_time.strftime("%H:%M:%S"),
                _format_hms(duration_seconds),
                f"{duration_hours:.4f}",
                entry.notes or "",
                f"{hourly_rate:.2f}",
                f"{amount:.2f}",
            ]
        )

    total_hours = total_seconds / 3600
    writer.writerow(
        [
            "",
            "",
            "Total:",
            _format_hms(total_seconds),
            f"{total_hours:.4f}",
            "",
            "",
            f"{total_amount:.2f}",
        ]
    )

    timesheet = Timesheet(
        user_id=current_user.id,
        client_id=client_id,
        month=month,
        year=year,
        period_start_utc=period_start_utc,
        period_end_utc=period_end_utc,
        period_timezone="UTC",
        period_type="monthly",
        total_hours=total_hours,
        total_amount=total_amount,
        csv_data=output.getvalue(),
    )
    db.session.add(timesheet)
    db.session.commit()

    return (
        jsonify(
            {
                "id": timesheet.id,
                "client_id": client_id,
                "client_name": client.name,
                "period_type": "monthly",
                "month": month,
                "year": year,
                "total_hours": round(total_hours, 4),
                "total_amount": round(total_amount, 2),
                "created_at": _ensure_utc(timesheet.created_at)
                .isoformat()
                .replace("+00:00", "Z"),
            }
        ),
        201,
    )


@timesheets.route("/api/timesheets", methods=["GET"])
@login_required
def get_timesheets():
    """Get all timesheets for the current user."""
    timesheets_list = (
        Timesheet.query.filter_by(user_id=current_user.id)
        .order_by(Timesheet.created_at.desc())
        .all()
    )
    return jsonify([_serialize_timesheet(t) for t in timesheets_list])


@timesheets.route("/api/timesheets/<int:timesheet_id>/download", methods=["GET"])
@login_required
def download_timesheet(timesheet_id):
    """Download a timesheet as CSV."""
    timesheet = Timesheet.query.filter_by(
        id=timesheet_id, user_id=current_user.id
    ).first()
    if not timesheet:
        return jsonify({"error": "Timesheet not found"}), 404

    client_name = _safe_client_filename(_client_name(timesheet))
    if (
        timesheet.period_type == "range"
        and timesheet.period_start_utc
        and timesheet.period_end_utc
    ):
        timezone_name = timesheet.period_timezone or "UTC"
        try:
            tz = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            tz = timezone.utc

        start_label = _ensure_utc(timesheet.period_start_utc).astimezone(tz).date()
        end_label = (
            _ensure_utc(timesheet.period_end_utc) - timedelta(microseconds=1)
        ).astimezone(tz).date()
        filename = f"{client_name}_{start_label}_to_{end_label}_timesheet.csv"
    else:
        month_name = calendar.month_name[timesheet.month]
        filename = f"{client_name}_{month_name}_{timesheet.year}_timesheet.csv"

    return Response(
        timesheet.csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@timesheets.route("/api/timesheets/<int:timesheet_id>", methods=["DELETE"])
@login_required
def delete_timesheet(timesheet_id):
    """Delete a timesheet."""
    timesheet = Timesheet.query.filter_by(
        id=timesheet_id, user_id=current_user.id
    ).first()
    if not timesheet:
        return jsonify({"error": "Timesheet not found"}), 404

    db.session.delete(timesheet)
    db.session.commit()
    return jsonify({"message": "Timesheet deleted successfully"}), 200
