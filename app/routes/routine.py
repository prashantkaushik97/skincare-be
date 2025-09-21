# app/routes/routine.py
from flask import Blueprint, request, jsonify
import os, json, requests
from app.utils.firebase import firebase_auth, firestore_client
from google.cloud import firestore
from datetime import datetime, timedelta

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
    r = r or {}
    time = r.get("time") or ["morning", "evening"]
    prod = r.get("products") or {}
    plan = r.get("plan") or {}
    if isinstance(prod, dict):
        am = prod.get("am") or []
        pm = prod.get("pm") or []
    else:
        am, pm = (prod or []), []
    def _clean(arr):
        out = []
        for p in arr:
            pid = (p.get("id") or "").strip()
            if pid:
                out.append({"id": pid})
        return out
    products = {"am": _clean(am), "pm": _clean(pm)}
    return {"time": time, "products": products, "plan": plan}

def _today_date_str():
    return datetime.utcnow().strftime("%Y-%m-%d")

def _month_range(year, month):
    start = datetime(year, month, 1)
    end = datetime(year + (month==12), 1 if month==12 else month+1, 1)
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days)]

# --------- New collection refs ----------
def _routine_doc(uid):
    # current routine per user (small, hot)
    return firestore_client.collection("user_routines").document(uid)

def _status_doc_id(uid, date_str):
    # flat collection for easy TTL/archival and CG queries
    return f"{uid}_{date_str}"

def _status_doc(date_str, uid):
    return firestore_client.collection("user_routine_status").document(_status_doc_id(uid, date_str))

# ----------------------------- OpenAI helper (unchanged) -----------------------------
def create_routine_openai(products):
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
            "morning": {"type": "ARRAY","items":{"type":"OBJECT","properties":{"name":{"type":"STRING"},"order":{"type":"NUMBER"}},"propertyOrdering":["name","order"]}},
            "evening": {"type": "ARRAY","items":{"type":"OBJECT","properties":{"name":{"type":"STRING"},"order":{"type":"NUMBER"}},"propertyOrdering":["name","order"]}}
        },
        "propertyOrdering": ["morning", "evening"]
    }
    payload = {"contents":[{"parts":[{"text": user_query}]}],
               "generationConfig":{"responseMimeType":"application/json","responseSchema":response_schema}}
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
    """
    Upserts the CURRENT routine to user_routines/{uid}.
    Body: { time?: ["morning","evening"], products: [{id: "..."}] }
    """
    uid, err = _bearer_uid_or_401()
    if err: return err
    try:
        data = request.get_json() or {}
        time = data.get("time", ["morning", "evening"])
        products = data.get("products", [])
        if not isinstance(products, list):
            return jsonify({"error": "products must be a list"}), 400

        doc_ref = _routine_doc(uid)
        snap = doc_ref.get()
        current = _normalize_routine(snap.to_dict())

        new_routine = {
            "time": time,
            "products": {
                "am": [{"id": (p.get("id") or "").strip()} for p in (data.get("products_am") or []) if (p.get("id") or "").strip()],
                "pm": [{"id": (p.get("id") or "").strip()} for p in (data.get("products_pm") or []) if (p.get("id") or "").strip()],
            } if any(k in data for k in ("products_am","products_pm")) else {
                # fallback if client still sends flat list -> treat as AM
                "am": [{"id": (p.get("id") or "").strip()} for p in products if (p.get("id") or "").strip()],
                "pm": current.get("products", {}).get("pm", [])
            },
            "plan": current.get("plan", {}),  # preserve plan unless caller overwrites explicitly
        }

        doc_ref.set(new_routine)
        return jsonify({"message": "Routine saved", "routine": new_routine}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routine_bp.route("/routine", methods=["GET"])
def get_routine():
    """
    Returns current routine from user_routines/{uid}.
    If old users.{routine} exists, migrates it once into user_routines/{uid}.
    """
    uid, err = _bearer_uid_or_401()
    if err: return err
    try:
        doc_ref = _routine_doc(uid)
        snap = doc_ref.get()

        if not snap.exists:
            # migrate from legacy users.{routine} if present
            legacy = firestore_client.collection("users").document(uid).get().to_dict() or {}
            legacy_norm = _normalize_routine(legacy.get("routine"))
            if legacy.get("routine"):
                doc_ref.set(legacy_norm)
            routine = legacy_norm
        else:
            routine = _normalize_routine(snap.to_dict())

        return jsonify({"routine": routine}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routine_bp.route("/routine/add/<product_id>", methods=["POST"])
def add_product_to_routine(product_id):
    uid, err = _bearer_uid_or_401()
    if err: return err

    product_id = (product_id or "").strip()
    slot = (request.args.get("time") or "am").strip().lower()
    if slot not in ("am", "pm"):
        return jsonify({"error": "time must be 'am' or 'pm'"}), 400
    if not product_id:
        return jsonify({"error": "Invalid product id"}), 400

    try:
        doc_ref = _routine_doc(uid)
        snap = doc_ref.get()
        routine = _normalize_routine(snap.to_dict())

        ids = { (p.get("id") or "").strip() for p in routine["products"][slot] }
        if product_id in ids:
            return jsonify({"error": "Product already in this slot"}), 400

        routine["products"][slot].append({"id": product_id})
        doc_ref.set(routine)
        return jsonify({"message": "Product added", "routine": routine}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routine_bp.route("/routine/remove/<product_id>", methods=["DELETE"])
def delete_product_from_routine(product_id):
    uid, err = _bearer_uid_or_401()
    if err: return err

    product_id = (product_id or "").strip()
    slot = request.args.get("time")
    if slot is not None:
        slot = slot.strip().lower()
        if slot not in ("am", "pm"):
            return jsonify({"error": "time must be 'am' or 'pm'"}), 400
    if not product_id:
        return jsonify({"error": "Invalid product id"}), 400

    try:
        doc_ref = _routine_doc(uid)
        snap = doc_ref.get()
        routine = _normalize_routine(snap.to_dict())

        def _strip(arr):
            return [p for p in arr if (p.get("id") or "").strip() != product_id]

        if slot:
            routine["products"][slot] = _strip(routine["products"][slot])
        else:
            routine["products"]["am"] = _strip(routine["products"]["am"])
            routine["products"]["pm"] = _strip(routine["products"]["pm"])

        doc_ref.set(routine)
        return jsonify({"message": "Product removed", "routine": routine}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routine_bp.route("/routine/generate", methods=["POST"])
def generate_routine():
    """
    Generates a plan and stores under user_routines/{uid}.plan (keeps products/time).
    """
    uid, err = _bearer_uid_or_401()
    if err: return err
    try:
        # Gather products from either user_products join or embedded somewhere else
        user_doc = firestore_client.collection("users").document(uid).get()
        user_data = user_doc.to_dict() or {}
        products_info = user_data.get("products", [])

        if not products_info:
            links = list(
                firestore_client.collection("user_products").where("uid", "==", uid).stream()
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

        doc_ref = _routine_doc(uid)
        snap = doc_ref.get()
        routine = _normalize_routine(snap.to_dict())
        routine["plan"] = generated_plan
        doc_ref.set(routine)
        print(f"Generated routine for user {uid}: {generated_plan}")
        return jsonify({
            "message": "New routine generated and saved.",
            "routine": generated_plan        
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routine_bp.route("/routine/status", methods=["POST"])
def mark_product_applied():
    """
    Mark product as applied for {uid, date, slot} in user_routine_status.
    Body: { "product_id": "...", "time": "am"/"pm", "date"?: "YYYY-MM-DD" }
    """
    uid, err = _bearer_uid_or_401()
    if err: return err
    data = request.get_json() or {}
    product_id = (data.get("product_id") or "").strip()
    slot = (data.get("time") or "am").strip().lower()
    if slot not in ("am", "pm"):
        return jsonify({"error": "time must be 'am' or 'pm'"}), 400
    if not product_id:
        return jsonify({"error": "Missing product_id"}), 400
    date_str = (data.get("date") or _today_date_str()).strip()

    try:
        status_ref = _status_doc(date_str, uid)
        status_doc = status_ref.get()
        status = status_doc.to_dict() if status_doc.exists else {"uid": uid, "date": date_str, "am": [], "pm": []}
        if product_id not in status.get(slot, []):
            status.setdefault(slot, []).append(product_id)
        status_ref.set(status)
        return jsonify({"message": "Product marked as applied", "status": status}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@routine_bp.route("/routine/status/unmark", methods=["POST"])
def unmark_product_applied():
    uid, err = _bearer_uid_or_401()
    if err: return err
    data = request.get_json() or {}
    product_id = (data.get("product_id") or "").strip()
    slot = (data.get("time") or "am").strip().lower()
    date_str = (data.get("date") or datetime.utcnow().strftime("%Y-%m-%d")).strip()
    if slot not in ("am","pm"): return jsonify({"error":"time must be 'am' or 'pm'"}), 400
    if not product_id: return jsonify({"error":"Missing product_id"}), 400

    try:
        status_ref = firestore_client.collection("user_routine_status").document(f"{uid}_{date_str}")
        status_doc = status_ref.get()
        status = status_doc.to_dict() if status_doc.exists else {"uid": uid, "date": date_str, "am": [], "pm": []}
        status[slot] = [pid for pid in status.get(slot, []) if pid != product_id]
        status_ref.set(status)
        return jsonify({"message": "Product unmarked", "status": status}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routine_bp.route("/routine/status", methods=["GET"])
def get_today_routine_status():
    """
    Returns status for ?date=YYYY-MM-DD (default today) + completion % using user_routines/{uid}.
    """
    uid, err = _bearer_uid_or_401()
    if err: return err
    date_str = (request.args.get("date") or _today_date_str()).strip()
    try:
        routine = _normalize_routine(_routine_doc(uid).get().to_dict())
        products = routine["products"]

        status_doc = _status_doc(date_str, uid).get()
        status = status_doc.to_dict() if status_doc.exists else {"am": [], "pm": []}

        def _completion(slot):
            total = len(products[slot])
            done = len([p for p in products[slot] if p["id"] in status.get(slot, [])])
            return (done / total * 100) if total else 0

        return jsonify({
            "date": date_str,
            "status": {"am": status.get("am", []), "pm": status.get("pm", [])},
            "completion": {"am": _completion("am"), "pm": _completion("pm")},
            "routine": products
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routine_bp.route("/routine/status/monthly", methods=["GET"])
def get_monthly_routine_status():
    """
    Aggregates daily status docs for given month; uses user_routines/{uid} to compute completion each day.
    Query: ?year=YYYY&month=MM
    """
    uid, err = _bearer_uid_or_401()
    if err: return err
    try:
        now = datetime.utcnow()
        year = int(request.args.get("year") or now.year)
        month = int(request.args.get("month") or now.month)
        days = _month_range(year, month)

        products = _normalize_routine(_routine_doc(uid).get().to_dict())["products"]

        results = []
        for day in days:
            date_str = day.strftime("%Y-%m-%d")
            sdoc = _status_doc(date_str, uid).get()
            status = sdoc.to_dict() if sdoc.exists else {"am": [], "pm": []}

            def _completion(slot):
                total = len(products[slot])
                done = len([p for p in products[slot] if p["id"] in status.get(slot, [])])
                return (done / total * 100) if total else 0

            results.append({
                "date": date_str,
                "status": {"am": status.get("am", []), "pm": status.get("pm", [])},
                "completion": {"am": _completion("am"), "pm": _completion("pm")}
            })

        return jsonify({"month": f"{year}-{month:02d}", "days": results}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
