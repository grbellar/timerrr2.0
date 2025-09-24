#!/usr/bin/env bash
# Build script for Render
# This script is executed during the build process

# Install dependencies
pip install -r requirements.txt

# Create database tables
python -c "from app import create_app; from app.models import db; app, socketio = create_app(); app.app_context().push(); db.create_all(); print('Database initialized')"