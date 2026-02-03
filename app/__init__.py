from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager
from app.models import db, User
import os
from sqlalchemy import inspect, text


def create_app():
    app = Flask(__name__)
    CORS(app)

    # Configuration
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "dev-secret-key-change-in-production"
    )

    # Use persistent disk for SQLite database in production, local file in development
    db_path = os.environ.get("DATABASE_PATH", "timerrr.db")

    # Ensure the directory exists for the database file
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize extensions
    db.init_app(app)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    # Initialize SocketIO
    from app.socketio_events import socketio

    socketio.init_app(app)

    # Register blueprints
    from app.auth import auth
    from app.main import main
    from app.client import client
    from app.timer import timer
    from app.entries import entries
    from app.stripe import stripe_bp
    from app.timesheets import timesheets

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(client)
    app.register_blueprint(timer)
    app.register_blueprint(entries)
    app.register_blueprint(stripe_bp)
    app.register_blueprint(timesheets)

    # Create database tables
    with app.app_context():
        db.create_all()
        _ensure_schema_updates()

    return app, socketio


def _ensure_schema_updates():
    """Apply lightweight schema updates for existing SQLite deployments."""
    inspector = inspect(db.engine)
    if "timesheets" not in inspector.get_table_names():
        return

    existing_columns = {c["name"] for c in inspector.get_columns("timesheets")}
    alter_statements = []

    if "period_start_utc" not in existing_columns:
        alter_statements.append(
            "ALTER TABLE timesheets ADD COLUMN period_start_utc DATETIME"
        )
    if "period_end_utc" not in existing_columns:
        alter_statements.append(
            "ALTER TABLE timesheets ADD COLUMN period_end_utc DATETIME"
        )
    if "period_timezone" not in existing_columns:
        alter_statements.append(
            "ALTER TABLE timesheets ADD COLUMN period_timezone VARCHAR(64)"
        )
    if "period_type" not in existing_columns:
        alter_statements.append("ALTER TABLE timesheets ADD COLUMN period_type VARCHAR(20)")

    if not alter_statements:
        return

    for statement in alter_statements:
        db.session.execute(text(statement))
    db.session.commit()
