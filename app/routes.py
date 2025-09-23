from flask import Blueprint, render_template

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')


@main.route('/timer')
def timer():
    return render_template('timer.html')

@main.route('/entries')
def entries():
    return render_template('entries.html')

@main.route('/timesheets')
def timesheets():
    return render_template('timesheets.html')

@main.route('/settings')
def settings():
    return render_template('settings.html')

@main.route('/api/hello')
def api_hello():
    return {'message': 'Flask API is running!'}
