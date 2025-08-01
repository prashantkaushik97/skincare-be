# app/utils/firebase.py
import firebase_admin
from firebase_admin import credentials, auth, firestore
import os

# cred = credentials.Certificate("serviceAccount.json")
# firebase_admin.initialize_app(cred)

# firebase_auth = auth  # alias for easy import

cred = credentials.Certificate("serviceAccount.json")
firebase_app = firebase_admin.initialize_app(cred)
firebase_auth = auth
firestore_client = firestore.client()