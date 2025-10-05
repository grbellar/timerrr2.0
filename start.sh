#!/bin/bash
source .venv/bin/activate
gunicorn --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker --workers 1 --bind 0.0.0.0:5001 wsgi:application --reload
