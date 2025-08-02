from flask import Blueprint, request, jsonify
from app.utils.firebase import firebase_auth, firestore_client

profile_bp = Blueprint("profile", __name__, url_prefix="/api")

@profile_bp.route("/profile", methods=["POST"])
def save_profile():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Missing token"}), 401

    id_token = auth_header.split(" ").pop()
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
    except Exception as e:
        return jsonify({"error": str(e)}), 401

    try:
        data = request.get_json()
        age = data.get("age", 18)
        skin_type = data.get("skinType", "")
        concerns = data.get("concerns", [])
        allergies = data.get("allergies", [])
        additional = data.get("additionalNotes", "")
        gender = data.get("gender", "")

        user_ref = firestore_client.collection("users").document(uid)
        user_ref.set({
            "skinProfile": {
                "age": age,
                "gender":gender,
                "skinType": skin_type,
                "concerns": concerns,
                "allergies": allergies,
                "additionalNotes": additional
            }
        }, merge=True)

        return jsonify({"message": "Profile saved"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
