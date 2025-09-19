# app/routes/routine.py
from flask import Blueprint, request, jsonify
import os, json, requests
from app.utils.firebase import firebase_auth, firestore_client
from google.cloud import firestore
API_KEY = os.getenv("GEMINI_API_KEY")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"

routine_bp = Blueprint("routine", __name__, url_prefix="/api")


# ----------------------------- Helpers -----------------------------

def _bearer_uid_or_401():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"error": "Missing or invalid Authorization header"}), 401)
    id_token = auth_header[len("Bearer "):].strip()
    try:
        decoded = firebase_auth.verify_id_token(id_token)
        return decoded["uid"], None
    except Exception as e:
        return None, (jsonify({"error": str(e)}), 401)


def _normalize_routine(r):
    """Always return a dict with time/products/plan keys."""
    r = r or {}
    time = r.get("time") or ["morning", "evening"]
    products = r.get("products") or []        # list of {"id": "..."}
    plan = r.get("plan") or {}                # {"morning":[{name,order}], "evening":[...]}
    return {"time": time, "products": products, "plan": plan}


def create_routine_openai(products):
    """
    Generates morning/evening routine using Gemini.
    products: list of dicts with at least name (id/brand/category optional)
    """
    product_list = "\n".join([f"- {p.get('name', 'Unknown Product')}" for p in products])
    user_query = (
        "I have the following products:\n"
        f"{product_list}\n\n"
        "Please create a simple and effective morning and evening skincare routine for me. "
        "For each routine, list the products to use and their recommended order. "
        "The order should be a number (1, 2, 3...). Provide the output in JSON format with "
        "'morning' and 'evening' keys."
    )

    response_schema = {
        "type": "OBJECT",
        "properties": {
            "morning": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING"},
                        "order": {"type": "NUMBER"}
                    },
                    "propertyOrdering": ["name", "order"]
                }
            },
            "evening": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING"},
                        "order": {"type": "NUMBER"}
                    },
                    "propertyOrdering": ["name", "order"]
                }
            }
        },
        "propertyOrdering": ["morning", "evening"]
    }

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }
    }

    try:
        resp = requests.post(f"{API_URL}?key={API_KEY}", json=payload)
        resp.raise_for_status()
        result = resp.json()
        generated_text = result["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(generated_text)
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return {"error": "Failed to generate routine from API."}
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Failed to parse API response: {e}")
        return {"error": "Invalid API response format."}


# ----------------------------- Routes -----------------------------

@routine_bp.route("/routine", methods=["POST"])
def save_routine():
    uid, err = _bearer_uid_or_401()
    if err: return err
    try:
        data = request.get_json() or {}
        time = data.get("time", ["morning", "evening"])
        products = data.get("products", [])
        if not isinstance(products, list):
            return jsonify({"error": "products must be a list"}), 400

        user_ref = firestore_client.collection("users").document(uid)
        snap = user_ref.get()
        current = _normalize_routine((snap.to_dict() or {}).get("routine"))
        new_routine = {
            "time": time,
            "products": [{"id": (p.get("id") or "").strip()} for p in products if (p.get("id") or "").strip()],
            "plan": current.get("plan", {}),
        }
        user_ref.set({"routine": new_routine}, merge=True)
        return jsonify({"message": "Routine saved", "routine": new_routine}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routine_bp.route("/routine", methods=["GET"])
def get_routine():
    """Retrieves a user's saved skincare routine: returns {routine:{time, products, plan}}"""
    uid, err = _bearer_uid_or_401()
    if err:
        return err
    try:
        doc = firestore_client.collection("users").document(uid).get()
        if not doc.exists:
            return jsonify({"routine": _normalize_routine({})}), 200
        routine = _normalize_routine(doc.to_dict().get("routine", {}))
        return jsonify({"routine": routine}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# app/routes/routine.py (replace the two routes)

@routine_bp.route("/routine/add/<product_id>", methods=["POST"])
def add_product_to_routine(product_id):
    """Adds a product ID to the user's routine, preserving time/plan."""
    uid, err = _bearer_uid_or_401()
    if err:
        return err

    product_id = (product_id or "").strip()
    if not product_id:
        return jsonify({"error": "Invalid product id"}), 400

    try:
        user_ref = firestore_client.collection("users").document(uid)
        snap = user_ref.get()
        data = snap.to_dict() or {}
        routine = _normalize_routine(data.get("routine"))

        # Normalize when checking
        existing_ids = {(p.get("id") or "").strip() for p in routine["products"]}
        if product_id in existing_ids:
            return jsonify({"error": "Product already in routine"}), 400

        routine["products"].append({"id": product_id})
        user_ref.set({"routine": routine}, merge=True)
        return jsonify({"message": "Product added to routine", "routine": routine}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routine_bp.route("/routine/remove/<product_id>", methods=["DELETE"])
def delete_product_from_routine(product_id):
    """Removes a product ID from the user's routine, preserving time/plan."""
    uid, err = _bearer_uid_or_401()
    if err:
        return err

    product_id = (product_id or "").strip()
    if not product_id:
        return jsonify({"error": "Invalid product id"}), 400

    try:
        user_ref = firestore_client.collection("users").document(uid)
        snap = user_ref.get()
        data = snap.to_dict() or {}
        routine = _normalize_routine(data.get("routine"))

        routine["products"] = [
            p for p in routine["products"]
            if (p.get("id") or "").strip() != product_id
        ]
        user_ref.set({"routine": routine}, merge=True)
        return jsonify({"message": "Product removed from routine", "routine": routine}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routine_bp.route("/routine/generate", methods=["POST"])
def generate_routine():
    """
    Generates a new skincare routine plan (morning/evening) based on the user's products.
    Writes under routine.plan, preserving routine.products membership.
    """
    uid, err = _bearer_uid_or_401()
    if err:
        return err
    try:
        user_ref = firestore_client.collection("users").document(uid)
        user_doc = user_ref.get()
        if not user_doc.exists:
            return jsonify({"error": "User not found"}), 404

        user_data = user_doc.to_dict() or {}

        # Try products embedded on user doc (if you store them there)
        products_info = user_data.get("products", [])

        # Fallback: join via user_products -> products collection
        if not products_info:
            links = list(
                firestore_client.collection("user_products")
                .where("uid", "==", uid)
                .stream()
            )
            product_ids = [d.to_dict().get("product_id") for d in links if d.to_dict().get("product_id")]
            products_info = []
            for pid in product_ids:
                pdoc = firestore_client.collection("products").document(pid).get()
                if pdoc.exists:
                    pd = pdoc.to_dict()
                    products_info.append({
                        "id": pid,
                        "name": pd.get("name", ""),
                        "category": pd.get("category", ""),
                        "brand": pd.get("brand", "")
                    })

        if not products_info:
            return jsonify({"error": "No products found to generate a routine from."}), 400

        generated_plan = create_routine_openai(products_info)
        if "error" in generated_plan:
            return jsonify(generated_plan), 500

        # Merge ONLY the plan; keep time/products intact
        user_ref.set({"routine": {"plan": generated_plan}}, merge=True)

        return jsonify({"message": "New routine generated and saved.", "routine": {"plan": generated_plan}}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
