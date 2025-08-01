# app/utils/firebase.py
import firebase_admin
from firebase_admin import auth, credentials
import os

cred = credentials.Certificate("serviceAccount.json")
firebase_admin.initialize_app(cred)

firebase_auth = auth  # alias for easy import
