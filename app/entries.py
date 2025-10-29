from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import db, Client, TimeEntry
from datetime import datetime, timezone, timedelta
from sqlalchemy import and_

entries = Blueprint("entries", __name__)


@entries.route("/api/entries", methods=["GET"])
@login_required
def get_entries():
    """Get paginated time entries with optional filtering"""
    # Get query parameters
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    client_id = request.args.get("client_id", type=int)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    # Debug logging
    print(
        f"Filtering entries - start_date: {start_date}, end_date: {end_date}, client_id: {client_id}"
    )

    # Build query
    query = TimeEntry.query.filter_by(user_id=current_user.id)

    # Apply filters
    if client_id:
        query = query.filter_by(client_id=client_id)

    if start_date:
        try:
            # Parse the date string (YYYY-MM-DD format)
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            # Set to beginning of day and account for timezone
            # Subtract a day to catch entries that might be from "yesterday" in UTC but "today" locally
            start_datetime = start_datetime.replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
            )
            start_datetime = start_datetime - timedelta(
                hours=24
            )  # Go back 24 hours to be inclusive
            query = query.filter(TimeEntry.start_time >= start_datetime)
            print(f"Filtering from: {start_datetime}")
        except (ValueError, TypeError) as e:
            print(f"Error parsing start_date: {e}")

    if end_date:
        try:
            # Parse the date string (YYYY-MM-DD format)
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
            # Set to end of day and account for timezone
            # Add a day to catch entries that might be from "tomorrow" in UTC but "today" locally
            end_datetime = end_datetime.replace(
                hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc
            )
            end_datetime = end_datetime + timedelta(
                hours=24
            )  # Go forward 24 hours to be inclusive
            query = query.filter(TimeEntry.start_time <= end_datetime)
            print(f"Filtering to: {end_datetime}")
        except (ValueError, TypeError) as e:
            print(f"Error parsing end_date: {e}")

    # Order by start_time descending (most recent first)
    query = query.order_by(TimeEntry.start_time.desc())

    # Paginate
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    print(f"Found {paginated.total} entries after filtering")

    # Debug: Show first entry's date if exists
    if paginated.items:
        first_entry = paginated.items[0]
        print(f"First entry start_time: {first_entry.start_time}")

    # Format results
    entries_list = []
    for entry in paginated.items:
        entry_data = {
            "id": entry.id,
            "client_id": entry.client_id,
            "client_name": entry.client.name if entry.client else "No Client",
            "start_time": entry.start_time.isoformat(),
            "end_time": entry.end_time.isoformat() if entry.end_time else None,
            "notes": entry.notes or "",
            "is_running": entry.is_running,
            "duration": entry.duration,
        }
        entries_list.append(entry_data)

    return jsonify(
        {
            "entries": entries_list,
            "total": paginated.total,
            "pages": paginated.pages,
            "current_page": page,
            "per_page": per_page,
        }
    )


@entries.route("/api/entries/<int:entry_id>", methods=["GET"])
@login_required
def get_entry(entry_id):
    """Get a specific time entry"""
    entry = TimeEntry.query.filter_by(id=entry_id, user_id=current_user.id).first()

    if not entry:
        return jsonify({"error": "Entry not found"}), 404

    return jsonify(
        {
            "id": entry.id,
            "client_id": entry.client_id,
            "client_name": entry.client.name if entry.client else "No Client",
            "start_time": entry.start_time.isoformat(),
            "end_time": entry.end_time.isoformat() if entry.end_time else None,
            "notes": entry.notes or "",
            "is_running": entry.is_running,
            "duration": entry.duration,
        }
    )


@entries.route("/api/entries/<int:entry_id>", methods=["PUT"])
@login_required
def update_entry(entry_id):
    """Update a time entry"""
    entry = TimeEntry.query.filter_by(id=entry_id, user_id=current_user.id).first()

    if not entry:
        return jsonify({"error": "Entry not found"}), 404

    data = request.get_json()

    # Update fields if provided
    if "client_id" in data:
        # Verify client belongs to user
        client = Client.query.filter_by(
            id=data["client_id"], user_id=current_user.id
        ).first()
        if client:
            entry.client_id = data["client_id"]

    if "start_time" in data:
        try:
            entry.start_time = datetime.fromisoformat(
                data["start_time"].replace("Z", "+00:00")
            )
        except ValueError:
            return jsonify({"error": "Invalid start_time format"}), 400

    if "end_time" in data:
        if data["end_time"] is None:
            entry.end_time = None
        else:
            try:
                entry.end_time = datetime.fromisoformat(
                    data["end_time"].replace("Z", "+00:00")
                )
            except ValueError:
                return jsonify({"error": "Invalid end_time format"}), 400

    if "notes" in data:
        entry.notes = data["notes"]

    db.session.commit()

    return jsonify(
        {
            "id": entry.id,
            "client_id": entry.client_id,
            "client_name": entry.client.name if entry.client else "No Client",
            "start_time": entry.start_time.isoformat(),
            "end_time": entry.end_time.isoformat() if entry.end_time else None,
            "notes": entry.notes or "",
            "is_running": entry.is_running,
            "duration": entry.duration,
        }
    )


@entries.route("/api/entries/<int:entry_id>", methods=["DELETE"])
@login_required
def delete_entry(entry_id):
    """Delete a time entry"""
    entry = TimeEntry.query.filter_by(id=entry_id, user_id=current_user.id).first()

    if not entry:
        return jsonify({"error": "Entry not found"}), 404

    db.session.delete(entry)
    db.session.commit()

    return jsonify({"message": "Entry deleted successfully"}), 200
