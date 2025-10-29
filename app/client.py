from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import db, Client, TierEnum

client = Blueprint("client", __name__)


@client.route("/api/clients", methods=["GET"])
@login_required
def get_clients():
    """Get all clients for the current user"""
    clients = Client.query.filter_by(user_id=current_user.id).all()
    return jsonify(
        [
            {
                "id": c.id,
                "name": c.name,
                "hourly_rate": c.hourly_rate,
                "created_at": c.created_at.isoformat(),
            }
            for c in clients
        ]
    )


@client.route("/api/clients", methods=["POST"])
@login_required
def create_client():
    """Create a new client"""
    data = request.get_json()
    name = data.get("name", "").strip()
    hourly_rate = data.get("hourly_rate", 0.0)

    if not name:
        return jsonify({"error": "Client name is required"}), 400

    # Check client limit for FREE tier users
    if current_user.tier == TierEnum.FREE:
        client_count = Client.query.filter_by(user_id=current_user.id).count()
        if client_count >= 3:
            return jsonify(
                {
                    "error": "Free plan limited to 3 clients. Upgrade to Pro for unlimited clients."
                }
            ), 403

    # Validate hourly rate
    try:
        hourly_rate = float(hourly_rate)
        if hourly_rate < 0:
            return jsonify({"error": "Hourly rate cannot be negative"}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid hourly rate"}), 400

    # Check if client already exists
    existing = Client.query.filter_by(name=name, user_id=current_user.id).first()
    if existing:
        return jsonify({"error": "Client with this name already exists"}), 400

    client = Client(name=name, user_id=current_user.id, hourly_rate=hourly_rate)
    db.session.add(client)
    db.session.commit()

    return jsonify(
        {
            "id": client.id,
            "name": client.name,
            "hourly_rate": client.hourly_rate,
            "created_at": client.created_at.isoformat(),
        }
    ), 201


@client.route("/api/clients/<int:client_id>", methods=["PUT"])
@login_required
def update_client(client_id):
    """Update an existing client"""
    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first()

    if not client:
        return jsonify({"error": "Client not found"}), 404

    data = request.get_json()
    name = data.get("name", "").strip()
    hourly_rate = data.get("hourly_rate", client.hourly_rate)

    if not name:
        return jsonify({"error": "Client name is required"}), 400

    # Validate hourly rate
    try:
        hourly_rate = float(hourly_rate)
        if hourly_rate < 0:
            return jsonify({"error": "Hourly rate cannot be negative"}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid hourly rate"}), 400

    # Check if another client has this name
    existing = (
        Client.query.filter_by(name=name, user_id=current_user.id)
        .filter(Client.id != client_id)
        .first()
    )
    if existing:
        return jsonify({"error": "Another client with this name already exists"}), 400

    client.name = name
    client.hourly_rate = hourly_rate
    db.session.commit()

    return jsonify(
        {
            "id": client.id,
            "name": client.name,
            "hourly_rate": client.hourly_rate,
            "created_at": client.created_at.isoformat(),
        }
    )


@client.route("/api/clients/<int:client_id>", methods=["DELETE"])
@login_required
def delete_client(client_id):
    """Delete a client"""
    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first()

    if not client:
        return jsonify({"error": "Client not found"}), 404

    db.session.delete(client)
    db.session.commit()

    return "", 204


@client.route("/api/clients/<int:client_id>", methods=["GET"])
@login_required
def get_client(client_id):
    """Get a single client by ID"""
    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first()

    if not client:
        return jsonify({"error": "Client not found"}), 404

    return jsonify(
        {
            "id": client.id,
            "name": client.name,
            "hourly_rate": client.hourly_rate,
            "created_at": client.created_at.isoformat(),
        }
    )
