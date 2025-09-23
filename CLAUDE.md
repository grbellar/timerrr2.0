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
- `/` - Main page serving the index template
- `/api/hello` - Sample JSON API endpoint

### Template System
Templates use Jinja2 inheritance:
- `base.html` defines the overall layout with navbar and footer
- Child templates extend base using `{% extends "base.html" %}` and override blocks