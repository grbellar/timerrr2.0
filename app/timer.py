from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import db, Client, TimeEntry
from datetime import datetime, timezone
from app.socketio_events import socketio

timer = Blueprint('timer', __name__)

@timer.route('/api/clients/timers', methods=['GET'])
@login_required
def get_client_timers():
    """Get all clients with their running timer status"""
    clients = Client.query.filter_by(user_id=current_user.id).all()

    result = []
    for client in clients:
        running_timer = client.get_running_timer()
        client_data = {
            'id': client.id,
            'name': client.name,
            'hourly_rate': client.hourly_rate,
            'timer': None
        }

        if running_timer:
            client_data['timer'] = {
                'id': running_timer.id,
                'start_time': running_timer.start_time.isoformat(),
                'notes': running_timer.notes or '',
                'is_running': True
            }

        result.append(client_data)

    return jsonify(result)

@timer.route('/api/clients/<int:client_id>/timer/start', methods=['POST'])
@login_required
def start_timer(client_id):
    """Start a timer for a specific client"""
    # Verify client belongs to user
    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first()
    if not client:
        return jsonify({'error': 'Client not found'}), 404

    # Check if timer already running
    existing_timer = client.get_running_timer()
    if existing_timer:
        return jsonify({'error': 'Timer already running for this client'}), 400

    # Create new time entry
    entry = TimeEntry(
        user_id=current_user.id,
        client_id=client_id,
        start_time=datetime.now(timezone.utc),
        notes=""
    )
    db.session.add(entry)
    db.session.commit()

    # Emit Socket.IO event to all user's connected devices
    room = f"user_{current_user.id}"
    socketio.emit('timer_started', {
        'timer_id': entry.id,
        'client_id': client_id,
        'client_name': client.name,
        'start_time': entry.start_time.isoformat(),
        'notes': entry.notes
    }, room=room)

    return jsonify({
        'id': entry.id,
        'client_id': client_id,
        'start_time': entry.start_time.isoformat(),
        'notes': entry.notes
    }), 201

@timer.route('/api/clients/<int:client_id>/timer/stop', methods=['PUT'])
@login_required
def stop_timer(client_id):
    """Stop the running timer for a specific client"""
    # Verify client belongs to user
    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first()
    if not client:
        return jsonify({'error': 'Client not found'}), 404

    # Find running timer
    entry = client.get_running_timer()
    if not entry:
        return jsonify({'error': 'No running timer found for this client'}), 400

    # Stop the timer
    entry.end_time = datetime.now(timezone.utc)

    # Update notes if provided
    data = request.get_json() or {}
    if 'notes' in data:
        entry.notes = data['notes']

    db.session.commit()

    # Emit Socket.IO event to all user's connected devices
    room = f"user_{current_user.id}"
    socketio.emit('timer_stopped', {
        'timer_id': entry.id,
        'client_id': client_id,
        'client_name': client.name,
        'end_time': entry.end_time.isoformat(),
        'duration': entry.duration
    }, room=room)

    return jsonify({
        'id': entry.id,
        'client_id': client_id,
        'end_time': entry.end_time.isoformat(),
        'duration': entry.duration,
        'notes': entry.notes
    })

@timer.route('/api/timers/<int:timer_id>/notes', methods=['PUT'])
@login_required
def update_timer_notes(timer_id):
    """Update notes for a running timer"""
    data = request.get_json()
    notes = data.get('notes', '')

    # Find timer and verify it belongs to user
    entry = TimeEntry.query.filter_by(
        id=timer_id,
        user_id=current_user.id,
        end_time=None
    ).first()

    if not entry:
        return jsonify({'error': 'Timer not found or already stopped'}), 404

    entry.notes = notes
    db.session.commit()

    # Emit Socket.IO event to all user's connected devices
    room = f"user_{current_user.id}"
    socketio.emit('notes_updated', {
        'timer_id': timer_id,
        'client_id': entry.client_id,
        'notes': notes
    }, room=room)

    return jsonify({
        'id': entry.id,
        'notes': entry.notes
    })

@timer.route('/api/timers/running', methods=['GET'])
@login_required
def get_running_timers():
    """Get all running timers for the current user"""
    timers = TimeEntry.query.filter_by(
        user_id=current_user.id,
        end_time=None
    ).all()

    result = []
    for timer in timers:
        result.append({
            'id': timer.id,
            'client_id': timer.client_id,
            'client_name': timer.client.name if timer.client else None,
            'start_time': timer.start_time.isoformat(),
            'notes': timer.notes or ''
        })

    return jsonify(result)