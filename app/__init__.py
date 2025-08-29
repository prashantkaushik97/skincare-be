from flask import Flask
from app.routes.auth import auth_bp
from app.routes.profile import profile_bp
from app.routes.routine import routine_bp
from app.routes.products import products_bp
from app.routes.health import health_bp
def create_app():
    app = Flask(__name__)
    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(routine_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(health_bp)

    return app