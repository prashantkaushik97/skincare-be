from flask import Blueprint, request, jsonify
from app.utils.firebase import firebase_auth, firestore_client


products_bp = Blueprint("products", __name__, url_prefix="/api")

@products_bp.route("/products", methods=["GET"])
def get_products():
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
        products_ref = firestore_client.collection("products")
        products = [doc.to_dict() for doc in products_ref.stream()]
        
        return jsonify({"products": products}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@products_bp.route("/products/<product_id>", methods=["GET"])
def get_product(product_id):
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
        product_ref = firestore_client.collection("products").document(product_id)
        product = product_ref.get()
        
        if not product.exists:
            return jsonify({"error": "Product not found"}), 404
        
        return jsonify({"product": product.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@products_bp.route("/products", methods=["POST"])
def add_product():
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
        product_data = {
            "name": data.get("name"),
            # "description": data.get("description"),
            # "price": data.get("price"),
            "category": data.get("category"),
            # "image_url": data.get("imageUrl")
        }

        products_ref = firestore_client.collection("products")
        products_ref.add(product_data)

        return jsonify({"message": "Product added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500