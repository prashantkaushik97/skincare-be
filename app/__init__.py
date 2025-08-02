from flask import Flask
from app.routes.auth import auth_bp
from app.routes.profile import profile_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)

    return app