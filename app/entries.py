from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import db, Client, TimeEntry
from datetime import datetime, timezone
from sqlalchemy import and_

entries = Blueprint('entries', __name__)

@entries.route('/api/entries', methods=['GET'])
@login_required
def get_entries():
    """Get paginated time entries with optional filtering"""
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    client_id = request.args.get('client_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Build query
    query = TimeEntry.query.filter_by(user_id=current_user.id)

    # Apply filters
    if client_id:
        query = query.filter_by(client_id=client_id)

    if start_date:
        try:
            start_datetime = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
            query = query.filter(TimeEntry.start_time >= start_datetime)
        except ValueError:
            pass

    if end_date:
        try:
            # Add 23:59:59 to end date to include the entire day
            end_datetime = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            query = query.filter(TimeEntry.start_time <= end_datetime)
        except ValueError:
            pass

    # Order by start_time descending (most recent first)
    query = query.order_by(TimeEntry.start_time.desc())

    # Paginate
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    # Format results
    entries_list = []
    for entry in paginated.items:
        entry_data = {
            'id': entry.id,
            'client_id': entry.client_id,
            'client_name': entry.client.name if entry.client else 'No Client',
            'start_time': entry.start_time.isoformat(),
            'end_time': entry.end_time.isoformat() if entry.end_time else None,
            'notes': entry.notes or '',
            'is_running': entry.is_running,
            'duration': entry.duration
        }
        entries_list.append(entry_data)

    return jsonify({
        'entries': entries_list,
        'total': paginated.total,
        'pages': paginated.pages,
        'current_page': page,
        'per_page': per_page
    })

@entries.route('/api/entries/<int:entry_id>', methods=['GET'])
@login_required
def get_entry(entry_id):
    """Get a specific time entry"""
    entry = TimeEntry.query.filter_by(
        id=entry_id,
        user_id=current_user.id
    ).first()

    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    return jsonify({
        'id': entry.id,
        'client_id': entry.client_id,
        'client_name': entry.client.name if entry.client else 'No Client',
        'start_time': entry.start_time.isoformat(),
        'end_time': entry.end_time.isoformat() if entry.end_time else None,
        'notes': entry.notes or '',
        'is_running': entry.is_running,
        'duration': entry.duration
    })

@entries.route('/api/entries/<int:entry_id>', methods=['PUT'])
@login_required
def update_entry(entry_id):
    """Update a time entry"""
    entry = TimeEntry.query.filter_by(
        id=entry_id,
        user_id=current_user.id
    ).first()

    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    data = request.get_json()

    # Update fields if provided
    if 'client_id' in data:
        # Verify client belongs to user
        client = Client.query.filter_by(id=data['client_id'], user_id=current_user.id).first()
        if client:
            entry.client_id = data['client_id']

    if 'start_time' in data:
        try:
            entry.start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid start_time format'}), 400

    if 'end_time' in data:
        if data['end_time'] is None:
            entry.end_time = None
        else:
            try:
                entry.end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid end_time format'}), 400

    if 'notes' in data:
        entry.notes = data['notes']

    db.session.commit()

    return jsonify({
        'id': entry.id,
        'client_id': entry.client_id,
        'client_name': entry.client.name if entry.client else 'No Client',
        'start_time': entry.start_time.isoformat(),
        'end_time': entry.end_time.isoformat() if entry.end_time else None,
        'notes': entry.notes or '',
        'is_running': entry.is_running,
        'duration': entry.duration
    })

@entries.route('/api/entries/<int:entry_id>', methods=['DELETE'])
@login_required
def delete_entry(entry_id):
    """Delete a time entry"""
    entry = TimeEntry.query.filter_by(
        id=entry_id,
        user_id=current_user.id
    ).first()

    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    db.session.delete(entry)
    db.session.commit()

    return jsonify({'message': 'Entry deleted successfully'}), 200