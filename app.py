"""Virtual Agronomist - application entry point.

Creates the Flask application, initialises the shared extensions, and registers
the route blueprints. All domain logic lives in the modules imported below.
"""
import os
from flask import Flask
from flask_cors import CORS

from core.config import Config
from core.extensions import db, bcrypt, jwt
from routes.auth import auth_bp
from routes.records import records_bp
from routes.chat import chat_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(app, origins="*")
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(records_bp)
    app.register_blueprint(chat_bp)

    with app.app_context():
        from core import models  # noqa: F401  (ensure models are registered before create_all)
        db.create_all()

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
