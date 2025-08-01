from flask import Blueprint, request, jsonify
from app.utils.firebase import firebase_auth, firestore_client
from google.cloud import firestore  # <-- add this import

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
        email = decoded_token.get("email", "")
        name = decoded_token.get("name", "")

        user_ref = firestore_client.collection("users").document(uid)
        user_ref.set({
            "email": email,
            "name": name,
            "lastLogin": firestore.SERVER_TIMESTAMP  # ✅ Fix here
        }, merge=True)

        return jsonify({"message": "Welcome!", "uid": uid}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 401
