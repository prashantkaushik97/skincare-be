from flask import Blueprint, request, jsonify
from app.utils.firebase import firebase_auth, firestore_client
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

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
        user_links = list(
            firestore_client.collection("user_products")
            .where("uid", "==", uid)
            .stream()
        )
        product_ids = list({
            doc.to_dict().get("product_id")
            for doc in user_links
            if doc.to_dict().get("product_id")
        })

        products = []
        for pid in product_ids:
            doc = firestore_client.collection("products").document(pid).get()
            if doc.exists:
                product_data = doc.to_dict()
                product_data["id"] = pid
                products.append(product_data)

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

        product_data = product.to_dict()
        product_data["id"] = product_id
        return jsonify({"product": product_data}), 200

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
        name = data.get("name")
        category = data.get("category")
        brand = data.get("brand") or ""


        if not name or not category:
            return jsonify({"error": "Missing required fields"}), 400

        # Step 1: Check if product exists
        products_ref = firestore_client.collection("products")
        query = products_ref.where("name", "==", name).where("category", "==", category).limit(1)
        result = query.stream()
        product_doc = next(result, None)

        if product_doc:
            product_id = product_doc.id
        else:
            # Step 2: Add new product
            new_product_ref = products_ref.document()
            new_product_ref.set({
                "name": name,
                "category": category,
                "brand": brand
            })
            product_id = new_product_ref.id

        # Step 3: Link product to user (ensure unique document per uid-product)
        user_products_ref = firestore_client.collection("user_products")
        link_doc_id = f"{uid}_{product_id}"
        link_doc = user_products_ref.document(link_doc_id)

        if not link_doc.get().exists:
            link_doc.set({
                "uid": uid,
                "product_id": product_id,
                "added_at": SERVER_TIMESTAMP
            })

        return jsonify({"message": "Product added/linked successfully", "product_id": product_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500
