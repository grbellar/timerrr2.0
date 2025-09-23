# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Setup
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py
# Or use the start script
./start.sh
```

### Running the Application
- Development server: `python app.py` (runs on port 5000 with debug mode)
- Production server: `gunicorn app:app`

## Architecture

This is a Flask web application using the Application Factory pattern with Blueprint-based routing.

### Core Structure
- **app.py**: Entry point that creates and runs the Flask app
- **app/__init__.py**: Application factory using `create_app()` pattern, configures CORS and registers blueprints
- **app/routes.py**: Main blueprint containing all routes (web and API endpoints)

### Key Design Patterns
1. **Application Factory Pattern**: The app is created via `create_app()` in `app/__init__.py`, allowing for flexible configuration and testing
2. **Blueprints**: Routes are organized using Flask Blueprints for modular code organization
3. **Template Inheritance**: Uses Jinja2 with a base template (`base.html`) that child templates extend

### Configuration
- Development config is hardcoded in `app/__init__.py` with SECRET_KEY
- Environment variables are stored in `.env` file
- CORS is enabled globally for all routes

### Current Endpoints
- `/` - Main page serving the index template (currently displays "Hello!")
- `/timer` - Timer page for tracking time with running timer display
- `/entries` - Time entries page for viewing and managing time logs
- `/api/hello` - Sample JSON API endpoint

### Template System
Templates use Jinja2 inheritance:
- `base.html` - Defines the overall layout with responsive navigation header
  - Uses Tailwind CSS via CDN for styling
  - Inter font family from Google Fonts
  - Mobile-responsive hamburger menu
  - Navigation includes: Timer, Entries, Timesheets, Settings, Logout
- Child templates extend base using `{% extends "base.html" %}` and override blocks
  - `index.html` - Simple landing page
  - `timer.html` - Time tracking interface with client name, timer display, description field, and clock out button
  - `entries.html` - Time entries list with filters (date range, client selector) and entry management (edit/delete)

### UI Framework & Styling
- **Tailwind CSS** loaded via CDN (not compiled)
- **Inter font** from Google Fonts
- **Responsive design** with mobile-first approach
- **Color scheme**: Gray-based with green/red accents for actions
- **Container max-width**: `max-w-6xl`
- **Common patterns**:
  - White cards on gray-50 background
  - Cards use: `bg-white rounded-lg shadow-sm border border-gray-200`
  - Mobile-responsive flexbox layouts with `flex-col sm:flex-row`