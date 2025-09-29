from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import current_user
from app.models import db, TimeEntry, Client
from datetime import datetime, timezone

socketio = SocketIO(cors_allowed_origins="*", async_mode='gevent')

@socketio.on('connect')
def handle_connect():
    """Handle client connection - join user-specific room"""
    if current_user.is_authenticated:
        room = f"user_{current_user.id}"
        join_room(room)
        emit('connected', {'status': 'Connected to timer updates'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if current_user.is_authenticated:
        room = f"user_{current_user.id}"
        leave_room(room)

@socketio.on('start_timer')
def handle_start_timer(data):
    """Start a timer for a specific client"""
    if not current_user.is_authenticated:
        return

    client_id = data.get('client_id')
    if not client_id:
        emit('error', {'message': 'Client ID required'})
        return

    # Verify client belongs to user
    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first()
    if not client:
        emit('error', {'message': 'Client not found'})
        return

    # Check if timer already running for this client
    existing_timer = client.get_running_timer()
    if existing_timer:
        emit('error', {'message': 'Timer already running for this client'})
        return

    # Create new time entry
    entry = TimeEntry(
        user_id=current_user.id,
        client_id=client_id,
        start_time=datetime.now(timezone.utc),
        notes=""
    )
    db.session.add(entry)
    db.session.commit()

    # Broadcast to all user's devices
    room = f"user_{current_user.id}"
    emit('timer_started', {
        'timer_id': entry.id,
        'client_id': client_id,
        'client_name': client.name,
        'start_time': entry.start_time.isoformat(),
        'notes': entry.notes
    }, room=room)

@socketio.on('stop_timer')
def handle_stop_timer(data):
    """Stop a running timer"""
    if not current_user.is_authenticated:
        return

    client_id = data.get('client_id')
    if not client_id:
        emit('error', {'message': 'Client ID required'})
        return

    # Verify client belongs to user
    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first()
    if not client:
        emit('error', {'message': 'Client not found'})
        return

    # Find running timer for this client
    entry = client.get_running_timer()
    if not entry:
        emit('error', {'message': 'No running timer found for this client'})
        return

    # Stop the timer
    entry.end_time = datetime.now(timezone.utc)
    db.session.commit()

    # Broadcast to all user's devices
    room = f"user_{current_user.id}"
    emit('timer_stopped', {
        'timer_id': entry.id,
        'client_id': client_id,
        'client_name': client.name,
        'end_time': entry.end_time.isoformat(),
        'duration': entry.duration
    }, room=room)

@socketio.on('update_notes')
def handle_update_notes(data):
    """Update notes for a running timer"""
    if not current_user.is_authenticated:
        return

    timer_id = data.get('timer_id')
    notes = data.get('notes', '')

    if not timer_id:
        emit('error', {'message': 'Timer ID required'})
        return

    # Find and verify timer belongs to user
    entry = TimeEntry.query.filter_by(
        id=timer_id,
        user_id=current_user.id,
        end_time=None
    ).first()

    if not entry:
        emit('error', {'message': 'Timer not found or already stopped'})
        return

    # Update notes
    entry.notes = notes
    db.session.commit()

    # Broadcast to all user's devices
    room = f"user_{current_user.id}"
    emit('notes_updated', {
        'timer_id': timer_id,
        'client_id': entry.client_id,
        'notes': notes
    }, room=room)