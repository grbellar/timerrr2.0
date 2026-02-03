# Repository Guidelines

## Project Structure & Module Organization
- `app/` contains the Flask application package. Key modules: `auth.py`, `main.py`, `client.py`, `timer.py`, `entries.py`, `timesheets.py`, `stripe.py`, and `models.py`.
- `app/templates/` holds Jinja HTML templates; `app/static/` holds CSS, images, and other static assets.
- Entry points: `run.py` (development server with Socket.IO) and `wsgi.py` (Gunicorn entry point with gevent monkey patching).
- Ops scripts: `start.sh` runs Gunicorn locally; `build.sh` installs deps for Render; `render.yaml` contains deployment config.

## Build, Test, and Development Commands
- `python -m venv .venv` and `source .venv/bin/activate` create/activate a local virtualenv.
- `pip install -r requirements.txt` installs runtime dependencies (a `uv.lock` is present if you prefer `uv`).
- `python run.py` starts the dev server with auto-reload on port `5001`.
- `./start.sh` runs Gunicorn with the WebSocket worker for local production-like runs.
- `./build.sh` is the Render build hook; it only installs dependencies.

## Coding Style & Naming Conventions
- Python uses 4-space indentation and snake_case for functions/variables.
- Keep Flask Blueprints and routes grouped by feature in `app/`.
- HTML templates follow Jinja conventions; shared layout lives in `app/templates/base.html`.
- CSS lives in `app/static/css/style.css`; keep class naming consistent with Tailwind utility usage in templates.

## Testing Guidelines
- No automated test suite is present in this repository.
- For changes, run the app and exercise the UI flows (timer, entries, timesheets, Stripe actions) against a local SQLite DB.
- If you add tests, place them under a new `tests/` directory and document how to run them.

## Commit & Pull Request Guidelines
- Commit history uses short, sentence-style messages (e.g., “Add WSGI”, “Fix SEO issues; Add social cards”). Follow that pattern.
- PRs should include: a concise summary, testing steps (`python run.py`, manual flows), and screenshots for UI changes.
- Call out any configuration changes (new env vars, Stripe settings, DB paths).

## Security & Configuration Tips
- `.env` is loaded in development via `python-dotenv` (see `run.py`). Typical keys: `SECRET_KEY`, `DATABASE_PATH`, and Stripe keys for payments.
- The default database path is `timerrr.db`; use a persistent disk path for production.
