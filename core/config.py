"""Application configuration.

Secrets are read from environment variables and are never written in code.
Set them locally with an .env file (see .env.example) or in the hosting
platform's environment variable settings.
"""
import os
from datetime import timedelta


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///agronomist.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET', 'agropintar-secret-2025')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)

    # Language model advisory layer
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/"
                  "models/gemini-2.5-flash:generateContent")
