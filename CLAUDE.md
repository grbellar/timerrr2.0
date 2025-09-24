# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask-based time tracking application called "timerrr" with a clean, minimal interface built using Tailwind CSS via CDN.

## Development Commands

### Setup and Run
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
# Or use the start script
./start.sh
```

The application runs on http://localhost:5000
    
### Virtual Environment
Always ensure the virtual environment is activated before running commands or installing packages.

## Architecture

### Application Structure
- **Flask factory pattern** - App is created via `create_app()` in `app/__init__.py`
- **Blueprint-based routing** - Routes are organized in `app/routes.py` using Flask blueprints
- **Template inheritance** - All HTML templates extend `base.html` for consistent layout
- **Tailwind CSS via CDN** - No build step required for styling
- **Real-time updates** - Socket.IO for WebSocket communication between client and server

### Key Routes
- `/` - Landing page
- `/timer` - Active timer interface with real-time updates
- `/entries` - Time entries list
- `/timesheets` - Timesheet view
- `/settings` - Settings page
- `/api/hello` - Example API endpoint

### Real-time Features with Socket.IO
The application uses Flask-SocketIO for real-time timer updates across all user devices:

#### Architecture
- **Server-side broadcasting** - Events are emitted from API endpoints in `app/timer.py` after database changes
- **User-specific rooms** - Each user joins a room `user_{id}` for isolated broadcasts
- **No page refresh needed** - All timer state changes sync instantly across devices

#### Implementation Details
- **WebSocket events** handled in `app/socketio_events.py`
- **Broadcasting from API** - Timer API endpoints emit Socket.IO events after DB updates
- **Room-based isolation** - Events broadcast to `user_{current_user.id}` room only
- **Event flow**:
  1. User clicks "Clock in" → API call to `/api/clients/{id}/timer/start`
  2. Server creates timer in DB, then broadcasts `timer_started` to user's room
  3. All user's connected devices receive event and update UI instantly

#### Event Types
- `timer_started` - Broadcast when a timer starts (includes timer_id, client_id, start_time)
- `timer_stopped` - Broadcast when a timer stops (includes timer_id, client_id, end_time)
- `notes_updated` - Broadcast when timer notes are updated (includes timer_id, notes)

#### Frontend Integration
- **Client-side Socket.IO** loaded via CDN in timer.html
- **JavaScript timer display** - Updates every second using setInterval
- **UTC timezone handling** - All timestamps use UTC with 'Z' suffix for proper JavaScript parsing
- **Auto-save notes** - Timer notes saved automatically with 500ms debouncing
- **No redundant emissions** - Client only makes API calls, server handles all Socket.IO broadcasts

### Frontend Design System
Templates follow a consistent design pattern documented in `app/templates/CLAUDE.md`:
- Mobile-first responsive design using Tailwind CSS
- Inter font family from Google Fonts
- White cards on gray-50 background
- Consistent spacing and typography scale
- No JavaScript frameworks - vanilla JS with Socket.IO for real-time features