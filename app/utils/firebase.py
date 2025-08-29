# app/utils/firebase.py
import os
import firebase_admin
from firebase_admin import credentials, auth, firestore

def _init_firebase():
    """
    Prefer Application Default Credentials (Cloud Run).
    Fall back to a JSON file for local/dev if present or env is set.
    """
    if firebase_admin._apps:
        return firebase_admin.get_app()

    json_from_env = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    json_local = "serviceAccount.json"

    if json_from_env and os.path.exists(json_from_env):
        cred = credentials.Certificate(json_from_env)
    elif os.path.exists(json_local):
        cred = credentials.Certificate(json_local)
    else:
        # Cloud Run path: uses the service account attached to the service
        cred = credentials.ApplicationDefault()

    return firebase_admin.initialize_app(cred)

app_ = _init_firebase()
firestore_client = firestore.client()
firebase_auth = auth
