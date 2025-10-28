from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user, login_required


def trial_required(f):
    """
    Decorator that ensures the user has access to the app.
    User must be logged in AND either have an active trial or Pro subscription.
    If trial has expired, redirects to upgrade page.
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.has_access:
            flash('Your free trial has expired. Please upgrade to continue using the app.', 'error')
            return redirect(url_for('main.settings'))
        return f(*args, **kwargs)
    return decorated_function
