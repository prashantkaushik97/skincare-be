from flask import Blueprint, request, jsonify
from app.utils.firebase import firebase_auth, firestore_client

routine_bp = Blueprint("routine", __name__, url_prefix="/api")

@routine_bp.route("/routine", methods=["POST"])
def save_routine():
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

        time = data.get("time", ["morning", "evening"])
        products = data.get("products", [])
        routine = {
            "time": time,
            "products": products
        }
        user_ref = firestore_client.collection("users").document(uid)
        user_ref.set({
            "routine": routine
        }, merge=True)

        return jsonify({"message": "Routine saved"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@routine_bp.route("/routine", methods=["GET"])
def get_routine():
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
        user_ref = firestore_client.collection("users").document(uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({"error": "User not found"}), 404

        routine = user_doc.to_dict().get("routine", {})
        return jsonify({"routine": routine}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@routine_bp.route("/routine/remove/<product_id>", methods=["DELETE"])
def delete_product_from_routine(product_id):
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
        user_ref = firestore_client.collection("users").document(uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({"error": "User not found"}), 404

        routine = user_doc.to_dict().get("routine", {})
        products = routine.get("products", [])

        # Remove product from routine
        products = [p for p in products if p.get("id") != product_id]
        routine["products"] = products

        user_ref.set({
            "routine": routine
        }, merge=True)

        return jsonify({"message": "Product removed from routine"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@routine_bp.route("/routine/add/<product_id>", methods=["POST"])
def add_product_to_routine(product_id):
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
        user_ref = firestore_client.collection("users").document(uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({"error": "User not found"}), 404

        routine = user_doc.to_dict().get("routine", {})
        products = routine.get("products", [])

        # Check if product already exists in routine
        if any(p.get("id") == product_id for p in products):
            return jsonify({"error": "Product already in routine"}), 400

        # Add product to routine
        products.append({"id": product_id})
        routine["products"] = products

        user_ref.set({
            "routine": routine
        }, merge=True)

        return jsonify({"message": "Product added to routine"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
