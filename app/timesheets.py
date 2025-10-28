from flask import Blueprint, request, jsonify, Response
from flask_login import login_required, current_user
from app.models import db, Client, TimeEntry, Timesheet
from datetime import datetime, timezone, timedelta
from sqlalchemy import and_, extract
import csv
import io
import calendar
from app.decorators import trial_required

timesheets = Blueprint('timesheets', __name__)

@timesheets.route('/api/timesheets/generate', methods=['POST'])
@trial_required
def generate_timesheet():
    """Generate a new timesheet for a client/month/year"""
    data = request.json

    client_id = data.get('client_id')
    month = data.get('month')
    year = data.get('year')

    # Validate inputs
    if not all([client_id, month, year]):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        client_id = int(client_id)
        month = int(month)
        year = int(year)

        if month < 1 or month > 12:
            return jsonify({'error': 'Invalid month'}), 400

        if year < 2020 or year > 2030:
            return jsonify({'error': 'Invalid year'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid data format'}), 400

    # Get client
    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first()
    if not client:
        return jsonify({'error': 'Client not found'}), 404

    # Check if timesheet already exists
    existing = Timesheet.query.filter_by(
        user_id=current_user.id,
        client_id=client_id,
        month=month,
        year=year
    ).first()

    if existing:
        return jsonify({'error': 'Timesheet already exists for this period'}), 409

    # Get date range for the month
    first_day = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day = datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59, tzinfo=timezone.utc)

    # Query time entries for this client and month
    entries = TimeEntry.query.filter(
        and_(
            TimeEntry.user_id == current_user.id,
            TimeEntry.client_id == client_id,
            TimeEntry.start_time >= first_day,
            TimeEntry.start_time <= last_day,
            TimeEntry.end_time.isnot(None)  # Only completed entries
        )
    ).order_by(TimeEntry.start_time).all()

    if not entries:
        return jsonify({'error': 'No time entries found for this period'}), 404

    # Generate CSV data
    output = io.StringIO()
    writer = csv.writer(output)

    # Write headers
    writer.writerow(['Date', 'Start Time', 'End Time', 'Duration (HH:MM:SS)', 'Duration (hrs)', 'Description', 'Rate', 'Amount'])

    total_seconds = 0
    total_amount = 0
    hourly_rate = client.hourly_rate or 0.0

    # Write entries
    for entry in entries:
        # Convert UTC times to local display (keeping UTC for consistency)
        date = entry.start_time.strftime('%Y-%m-%d')
        start_time = entry.start_time.strftime('%H:%M:%S')
        end_time = entry.end_time.strftime('%H:%M:%S') if entry.end_time else ''

        # Calculate duration
        duration_seconds = entry.duration if entry.duration else 0
        duration_hours = duration_seconds / 3600

        # Format duration as HH:MM:SS
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        seconds = int(duration_seconds % 60)
        duration_formatted = f'{hours:02d}:{minutes:02d}:{seconds:02d}'

        # Calculate amount based on exact seconds
        amount = duration_hours * hourly_rate

        total_seconds += duration_seconds
        total_amount += amount

        writer.writerow([
            date,
            start_time,
            end_time,
            duration_formatted,
            f'{duration_hours:.4f}',  # More precision for hours
            entry.notes or '',
            f'{hourly_rate:.2f}',
            f'{amount:.2f}'
        ])

    # Calculate totals
    total_hours = total_seconds / 3600
    total_hours_int = int(total_seconds // 3600)
    total_minutes = int((total_seconds % 3600) // 60)
    total_secs = int(total_seconds % 60)
    total_duration_formatted = f'{total_hours_int:02d}:{total_minutes:02d}:{total_secs:02d}'

    # Write totals row
    writer.writerow(['', '', 'Total:', total_duration_formatted, f'{total_hours:.4f}', '', '', f'{total_amount:.2f}'])

    csv_data = output.getvalue()

    # Create timesheet record (total_hours calculated from total_seconds for precision)
    timesheet = Timesheet(
        user_id=current_user.id,
        client_id=client_id,
        month=month,
        year=year,
        total_hours=total_hours,  # This now uses exact seconds-based calculation
        total_amount=total_amount,
        csv_data=csv_data
    )

    db.session.add(timesheet)
    db.session.commit()

    return jsonify({
        'id': timesheet.id,
        'client_id': client_id,
        'client_name': client.name,
        'month': month,
        'year': year,
        'total_hours': round(total_hours, 4),  # More precision for hours
        'total_amount': round(total_amount, 2),
        'created_at': timesheet.created_at.isoformat() + 'Z'
    }), 201


@timesheets.route('/api/timesheets', methods=['GET'])
@trial_required
def get_timesheets():
    """Get all timesheets for the current user"""
    timesheets_list = Timesheet.query.filter_by(user_id=current_user.id).order_by(Timesheet.created_at.desc()).all()

    return jsonify([{
        'id': t.id,
        'client_id': t.client_id,
        'client_name': t.client.name,
        'month': t.month,
        'year': t.year,
        'total_hours': round(t.total_hours, 4),  # More precision for hours
        'total_amount': round(t.total_amount, 2),
        'created_at': t.created_at.isoformat() + 'Z'
    } for t in timesheets_list])


@timesheets.route('/api/timesheets/<int:timesheet_id>/download', methods=['GET'])
@trial_required
def download_timesheet(timesheet_id):
    """Download a timesheet as CSV"""
    timesheet = Timesheet.query.filter_by(id=timesheet_id, user_id=current_user.id).first()

    if not timesheet:
        return jsonify({'error': 'Timesheet not found'}), 404

    # Get month name for filename
    month_name = calendar.month_name[timesheet.month]
    filename = f"{timesheet.client.name}_{month_name}_{timesheet.year}_timesheet.csv"

    # Return CSV as downloadable file
    return Response(
        timesheet.csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@timesheets.route('/api/timesheets/<int:timesheet_id>', methods=['DELETE'])
@trial_required
def delete_timesheet(timesheet_id):
    """Delete a timesheet"""
    timesheet = Timesheet.query.filter_by(id=timesheet_id, user_id=current_user.id).first()

    if not timesheet:
        return jsonify({'error': 'Timesheet not found'}), 404

    db.session.delete(timesheet)
    db.session.commit()

    return jsonify({'message': 'Timesheet deleted successfully'}), 200