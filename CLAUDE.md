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
The application uses Flask-SocketIO for real-time timer updates:
- **WebSocket events** handled in `app/socketio_events.py`
- **Timer synchronization** - All clients see timer updates in real-time
- **Auto-save notes** - Timer notes are saved automatically with debouncing
- **Event types**:
  - `timer_started` - Broadcast when a timer starts
  - `timer_stopped` - Broadcast when a timer stops
  - `notes_updated` - Broadcast when timer notes are updated
- **Client-side Socket.IO** loaded via CDN in timer.html
- **JavaScript timer display** - Updates every second using setInterval
- **UTC timezone handling** - All timestamps use UTC with 'Z' suffix for proper JavaScript parsing

### Frontend Design System
Templates follow a consistent design pattern documented in `app/templates/CLAUDE.md`:
- Mobile-first responsive design using Tailwind CSS
- Inter font family from Google Fonts
- White cards on gray-50 background
- Consistent spacing and typography scale
- No JavaScript frameworks - vanilla JS with Socket.IO for real-time features