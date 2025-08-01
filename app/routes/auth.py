# app/routes/auth.py
from flask import Blueprint, request, jsonify
from app.utils.firebase import firebase_auth

auth_bp = Blueprint("auth", __name__, url_prefix="/api")

@auth_bp.route("/login", methods=["POST"])
def login():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Missing token"}), 401

    id_token = auth_header.split(" ").pop()
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
        return jsonify({"message": "Welcome!", "uid": uid}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 401
