from flask import Blueprint, render_template, redirect, url_for, send_from_directory, current_app
from flask_login import login_required, current_user
from app.models import Client

main = Blueprint('main', __name__)

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.timer'))
    return render_template('index.html')

@main.route('/timer')
@login_required
def timer():
    # Get all clients for the current user with their timer status
    clients = Client.query.filter_by(user_id=current_user.id).all()

    client_timers = []
    for client in clients:
        running_timer = client.get_running_timer()
        client_timers.append({
            'client': client,
            'running_timer': running_timer
        })

    return render_template('timer.html', client_timers=client_timers)

@main.route('/entries')
@login_required
def entries():
    return render_template('entries.html')

@main.route('/timesheets')
@login_required
def timesheets():
    return render_template('timesheets.html')

@main.route('/settings')
@login_required
def settings():
    clients = Client.query.filter_by(user_id=current_user.id).all()
    return render_template('settings.html', clients=clients)

@main.route('/api/hello')
@login_required
def api_hello():
    return {'message': 'Flask API is running!', 'user': current_user.email}

@main.route('/robots.txt')
def robots_txt():
    return send_from_directory(current_app.static_folder, 'robots.txt')

@main.route('/sitemap.xml')
def sitemap_xml():
    return send_from_directory(current_app.static_folder, 'sitemap.xml')
