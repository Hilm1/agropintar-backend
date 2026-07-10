"""Shared Flask extension instances.

Kept in their own module so that every other module can import them
without creating circular imports back to app.py.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
bcrypt = Bcrypt()
jwt = JWTManager()
