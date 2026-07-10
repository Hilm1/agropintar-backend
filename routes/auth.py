"""Authentication routes: register, login, profile."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from core.extensions import db, bcrypt
from core.models import User

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    d = request.get_json()
    if not all(k in d for k in ['name', 'email', 'password']):
        return jsonify({'error': 'Name, email and password are required.'}), 400
    if User.query.filter_by(email=d['email']).first():
        return jsonify({'error': 'An account with this email already exists.'}), 409
    u = User(name=d['name'], email=d['email'],
             password=bcrypt.generate_password_hash(d['password']).decode(),
             location=d.get('location', 'Kuala Lumpur'),
             lat=d.get('lat', 3.1390), lon=d.get('lon', 101.6869))
    db.session.add(u)
    db.session.commit()
    return jsonify({'token': create_access_token(identity=str(u.id)),
                    'user': {'id': u.id, 'name': u.name, 'email': u.email,
                             'location': u.location}}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    d = request.get_json()
    u = User.query.filter_by(email=d.get('email', '')).first()
    if not u or not bcrypt.check_password_hash(u.password, d.get('password', '')):
        return jsonify({'error': 'Invalid email or password.'}), 401
    return jsonify({'token': create_access_token(identity=str(u.id)),
                    'user': {'id': u.id, 'name': u.name, 'email': u.email,
                             'location': u.location}}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    u = User.query.get(int(get_jwt_identity()))
    if not u:
        return jsonify({'error': 'Not found.'}), 404
    return jsonify({'id': u.id, 'name': u.name, 'email': u.email, 'location': u.location}), 200


@auth_bp.route('/update', methods=['PUT'])
@jwt_required()
def update_profile():
    u = User.query.get(int(get_jwt_identity()))
    d = request.get_json()
    if 'name' in d:
        u.name = d['name']
    if 'location' in d:
        u.location = d['location']
    db.session.commit()
    return jsonify({'message': 'Profile updated.'}), 200
