import os
from functools import wraps

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from app.models import Client, User, db

auth = Blueprint("auth", __name__)


DEFAULT_ADMIN_EMAILS = {"ayokayitsfine@gmail.com"}


def admin_emails():
    raw = os.environ.get("ADMIN_EMAILS", "")
    extra = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return DEFAULT_ADMIN_EMAILS | extra


def is_admin_user(user):
    return (
        user is not None
        and getattr(user, "is_authenticated", False)
        and (user.email or "").lower() in admin_emails()
    )


def access_required(view):
    """Allow only Pro subscribers, users in trial, and admins.

    For API calls (paths starting with /api/), returns 403 JSON.
    For browser routes, redirects to /settings with a flash message.
    """

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.is_authenticated and (
            is_admin_user(current_user) or current_user.has_access
        ):
            return view(*args, **kwargs)

        if request.path.startswith("/api/"):
            return (
                jsonify(
                    {
                        "error": "trial_expired",
                        "message": "Your free trial has ended. Upgrade to Pro to continue.",
                    }
                ),
                403,
            )

        flash("Your free trial has ended. Upgrade to Pro to continue.", "warning")
        return redirect(url_for("main.settings"))

    return wrapped


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.timer"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get("next")
            return redirect(next_page) if next_page else redirect(url_for("main.timer"))
        else:
            flash("Invalid email or password", "error")

    return render_template("login.html")


@auth.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.timer"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if User.query.filter_by(email=email).first():
            flash("Email already registered", "error")
            return redirect(url_for("auth.register"))

        user = User(email=email)
        user.set_password(password)
        user.start_trial()
        db.session.add(user)
        db.session.commit()

        login_user(user)
        create_default_client(user)

        return redirect(url_for("main.timer"))

    return render_template("register.html")


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


def create_default_client(user: User):
    client = Client(
        user_id=user.id, name="Your first client. Change the name in Settings."
    )
    db.session.add(client)
    db.session.commit()
