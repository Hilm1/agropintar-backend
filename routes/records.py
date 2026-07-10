"""Soil record routes: crop list and full CRUD, including recommendation generation."""
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from core.extensions import db
from core.models import User, SoilRecord, Prescription, record_to_dict
from domain.crops import CROPS
from domain.weather import get_weather
from domain.recommendation import get_prescription, get_safety_note, RULE_VERSION
from domain import advisory

records_bp = Blueprint('records', __name__, url_prefix='/api')

REQUIRED = ['crop_name', 'ph', 'nitrogen', 'phosphorus', 'potassium']


@records_bp.route('/crops', methods=['GET'])
def get_crops():
    return jsonify(CROPS), 200


@records_bp.route('/records', methods=['GET'])
@jwt_required()
def list_records():
    uid = int(get_jwt_identity())
    rows = SoilRecord.query.filter_by(user_id=uid).order_by(SoilRecord.recorded_at.desc()).all()
    return jsonify([record_to_dict(r) for r in rows]), 200


@records_bp.route('/records/<int:rid>', methods=['GET'])
@jwt_required()
def get_record(rid):
    r = SoilRecord.query.filter_by(id=rid, user_id=int(get_jwt_identity())).first()
    if not r:
        return jsonify({'error': 'Not found.'}), 404
    return jsonify(record_to_dict(r)), 200


@records_bp.route('/records', methods=['POST'])
@jwt_required()
def create_record():
    uid = int(get_jwt_identity())
    user = User.query.get(uid)
    d = request.get_json()
    if not all(k in d for k in REQUIRED):
        return jsonify({'error': 'All fields required.'}), 400

    loc_type = d.get('location_type', 'outdoor')
    r = SoilRecord(user_id=uid, crop_name=d['crop_name'], ph=float(d['ph']),
                   nitrogen=float(d['nitrogen']), phosphorus=float(d['phosphorus']),
                   potassium=float(d['potassium']), location_type=loc_type)
    db.session.add(r)
    db.session.flush()

    w = get_weather(user.lat, user.lon)
    rx = get_prescription(d, d['crop_name'], w, loc_type)          # rules decide
    note = advisory.explain(rx, d['crop_name'], d, loc_type)       # LLM only explains

    p = Prescription(record_id=r.id, fertilizer_name=rx['fertilizer_name'],
                     quantity=rx['quantity'], unit=rx['unit'], method=rx['method'],
                     frequency=rx['frequency'], note=note,
                     safety_note=get_safety_note(rx['fertilizer_name']),
                     rule_version=RULE_VERSION,
                     weather_temp=w['temperature'], weather_humidity=w['humidity'],
                     weather_rainfall=w['rainfall'])
    db.session.add(p)
    db.session.commit()
    return jsonify(record_to_dict(r)), 201


@records_bp.route('/records/<int:rid>', methods=['PUT'])
@jwt_required()
def update_record(rid):
    uid = int(get_jwt_identity())
    user = User.query.get(uid)
    r = SoilRecord.query.filter_by(id=rid, user_id=uid).first()
    if not r:
        return jsonify({'error': 'Not found.'}), 404

    d = request.get_json()
    if 'crop_name' in d:
        r.crop_name = d['crop_name']
    for field in ['ph', 'nitrogen', 'phosphorus', 'potassium']:
        if field in d:
            setattr(r, field, float(d[field]))
    if 'location_type' in d:
        r.location_type = d['location_type']

    w = get_weather(user.lat, user.lon)
    soil = {'ph': r.ph, 'nitrogen': r.nitrogen, 'phosphorus': r.phosphorus,
            'potassium': r.potassium}
    rx = get_prescription(soil, r.crop_name, w, r.location_type)
    note = advisory.explain(rx, r.crop_name, soil, r.location_type)

    p = r.prescription
    if p:
        p.fertilizer_name = rx['fertilizer_name']
        p.quantity = rx['quantity']
        p.unit = rx['unit']
        p.method = rx['method']
        p.frequency = rx['frequency']
        p.note = note
        p.safety_note = get_safety_note(rx['fertilizer_name'])
        p.rule_version = RULE_VERSION
        p.weather_temp = w['temperature']
        p.weather_humidity = w['humidity']
        p.weather_rainfall = w['rainfall']
        p.generated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Updated.'}), 200


@records_bp.route('/records/<int:rid>', methods=['DELETE'])
@jwt_required()
def delete_record(rid):
    r = SoilRecord.query.filter_by(id=rid, user_id=int(get_jwt_identity())).first()
    if not r:
        return jsonify({'error': 'Not found.'}), 404
    db.session.delete(r)
    db.session.commit()
    return jsonify({'message': 'Deleted.'}), 200
