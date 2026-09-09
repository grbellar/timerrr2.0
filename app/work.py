"""Browser and scoped bearer-token access to work sessions."""

import hashlib
import secrets
from datetime import timedelta

from flask import Blueprint, jsonify, render_template, request, session
from flask_login import current_user, login_required

from app import work_service as service
from app.auth import is_admin_user
from app.models import AgentToken, Client, User, WorkDraft, WorkSession, db

work_bp = Blueprint("work", __name__)
SCOPES = {"work:read", "work:write", "draft:write"}


def csrf_token():
    if "work_csrf" not in session:
        session["work_csrf"] = secrets.token_urlsafe(32)
    return session["work_csrf"]


def csrf_valid():
    supplied = request.headers.get("X-CSRF-Token", "")
    return bool(session.get("work_csrf")) and secrets.compare_digest(
        supplied, session["work_csrf"]
    )


@work_bp.errorhandler(service.WorkError)
def handle_work_error(error):
    return jsonify({"error": str(error)}), error.status


@work_bp.after_request
def private_response(response):
    if request.path.startswith("/api/agent") or request.path == "/work":
        response.headers["Cache-Control"] = "no-store"
    return response


@work_bp.get("/work")
@login_required
def workspace():
    return render_template(
        "work.html",
        csrf_token=csrf_token(),
        clients=Client.query.filter_by(user_id=current_user.id).all(),
    )


@work_bp.route("/api/agent-tokens", methods=["GET", "POST"])
@login_required
def tokens():
    if request.method == "GET":
        return jsonify(
            {
                "tokens": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "scopes": t.scopes.split(),
                        "expires_at": service.iso(t.expires_at),
                        "revoked_at": service.iso(t.revoked_at),
                    }
                    for t in AgentToken.query.filter_by(user_id=current_user.id)
                    .order_by(AgentToken.id.desc())
                    .all()
                ]
            }
        )
    if not csrf_valid():
        raise service.WorkError("Refresh the page and try again.", 403)
    if not (current_user.has_access or is_admin_user(current_user)):
        raise service.WorkError("An active trial or subscription is required.", 403)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise service.WorkError("Expected a JSON object.")
    name = service.string(data, "name")
    scopes = data.get("scopes", [])
    if (
        not isinstance(scopes, list)
        or not scopes
        or any(not isinstance(s, str) or s not in SCOPES for s in scopes)
    ):
        raise service.WorkError("Select valid token permissions.")
    raw = "tmr_" + secrets.token_urlsafe(32)
    token = AgentToken(
        user_id=current_user.id,
        name=name,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        scopes=" ".join(sorted(set(scopes))),
        expires_at=service.now() + timedelta(days=90),
    )
    db.session.add(token)
    db.session.commit()
    return jsonify(
        {"token": raw, "id": token.id, "expires_at": service.iso(token.expires_at)}
    ), 201


@work_bp.delete("/api/agent-tokens/<int:token_id>")
@login_required
def revoke_token(token_id):
    if not csrf_valid():
        raise service.WorkError("Refresh the page and try again.", 403)
    token = AgentToken.query.filter_by(id=token_id, user_id=current_user.id).first()
    if not token:
        raise service.WorkError("Token not found.", 404)
    token.revoked_at = service.now()
    db.session.commit()
    return jsonify({"revoked": True})


def principal(scope):
    authorization = request.headers.get("Authorization")
    if authorization:
        if not authorization.startswith("Bearer ") or len(authorization) > 200:
            raise service.WorkError("Invalid bearer token.", 401)
        hashed = hashlib.sha256(authorization[7:].encode()).hexdigest()
        token = AgentToken.query.filter_by(token_hash=hashed, revoked_at=None).first()
        if not token or token.expires_at <= service.now():
            raise service.WorkError("Token expired or invalid.", 401)
        user = db.session.get(User, token.user_id)
        if scope not in token.scopes.split():
            raise service.WorkError("Token does not have the required permission.", 403)
        source = f"token:{token.id}"
    else:
        if not current_user.is_authenticated:
            raise service.WorkError("Authentication required.", 401)
        if not csrf_valid():
            raise service.WorkError("Refresh the page and try again.", 403)
        user, source = current_user, "browser"
    if not user or not (user.has_access or is_admin_user(user)):
        raise service.WorkError("An active trial or subscription is required.", 403)
    return user.id, source


@work_bp.post("/api/agent/<action>")
def agent_action(action):
    read_actions = {
        "list_clients",
        "get_active_work",
        "get_work",
        "list_work",
        "get_draft",
        "list_drafts",
    }
    write_actions = {
        "start_work",
        "record_work_event",
        "finish_work",
        "draft_timesheet",
        "approve_draft",
    }
    if action not in read_actions | write_actions:
        raise service.WorkError("Unknown action.", 404)
    request.max_content_length = 256000
    if request.content_length and request.content_length > 256000:
        raise service.WorkError("Request too large.", 413)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise service.WorkError("Expected a JSON object.")
    scope = (
        "work:read"
        if action in read_actions
        else "draft:write"
        if action == "draft_timesheet"
        else "work:write"
    )
    user_id, source = principal(scope)
    if action == "list_clients":
        return jsonify(
            {
                "clients": [
                    {"id": c.id, "name": c.name}
                    for c in Client.query.filter_by(user_id=user_id).all()
                ]
            }
        )
    if action in ("get_active_work", "list_work"):
        query = WorkSession.query.filter_by(user_id=user_id)
        if action == "get_active_work":
            query = query.filter_by(finished_at=None)
        before_id = data.get("before_id")
        if before_id is not None:
            query = query.filter(WorkSession.id < service.integer(data, "before_id"))
        items = query.order_by(WorkSession.id.desc()).limit(51).all()
        return jsonify(
            {
                "work": [service.receipt(w) for w in items[:50]],
                "next_before_id": items[49].id if len(items) > 50 else None,
            }
        )
    if action == "get_work":
        return jsonify(
            {
                "work": service.receipt(
                    service.owned_work(user_id, service.integer(data, "work_id"))
                )
            }
        )
    if action == "list_drafts":
        return jsonify(
            {
                "drafts": [
                    {
                        "id": d.id,
                        "created_at": service.iso(d.created_at),
                        "approved_at": service.iso(d.approved_at),
                    }
                    for d in WorkDraft.query.filter_by(user_id=user_id)
                    .order_by(WorkDraft.id.desc())
                    .limit(50)
                    .all()
                ]
            }
        )
    if action == "get_draft":
        draft = WorkDraft.query.filter_by(
            id=service.integer(data, "draft_id"), user_id=user_id
        ).first()
        if not draft:
            raise service.WorkError("Draft not found.", 404)
        return jsonify({"draft": service.serialize_draft(draft)})
    result = service.execute(user_id, action, data, source)
    from app.socketio_events import socketio

    socketio.emit("work_updated", {"action": action}, room=f"user_{user_id}")
    return jsonify(result)
