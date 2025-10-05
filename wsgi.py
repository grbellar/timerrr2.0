"""
WSGI entry point with proper gevent monkey-patching.
This MUST be the entry point for gunicorn to ensure monkey-patching happens first.
"""
from gevent import monkey
# Patch everything before any other imports
monkey.patch_all()

# Now safe to import the app
from run import app, socketio

# For gunicorn, we need the WSGI application
application = app
