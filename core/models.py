"""Database models: User, SoilRecord, and Prescription."""
from datetime import datetime
from core.extensions import db


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(100), default='Kuala Lumpur')
    lat = db.Column(db.Float, default=3.1390)
    lon = db.Column(db.Float, default=101.6869)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    records = db.relationship('SoilRecord', backref='user', lazy=True,
                              cascade='all, delete-orphan')


class SoilRecord(db.Model):
    __tablename__ = 'soil_records'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    crop_name = db.Column(db.String(100), nullable=False)
    ph = db.Column(db.Float, nullable=False)
    nitrogen = db.Column(db.Float, nullable=False)
    phosphorus = db.Column(db.Float, nullable=False)
    potassium = db.Column(db.Float, nullable=False)
    location_type = db.Column(db.String(10), default='outdoor')
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    prescription = db.relationship('Prescription', backref='record', uselist=False,
                                   cascade='all, delete-orphan')


class Prescription(db.Model):
    __tablename__ = 'prescriptions'
    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey('soil_records.id'), nullable=False)
    fertilizer_name = db.Column(db.String(100))
    quantity = db.Column(db.String(50))
    unit = db.Column(db.String(30))
    method = db.Column(db.String(300))
    frequency = db.Column(db.String(100))
    note = db.Column(db.Text)
    safety_note = db.Column(db.Text)
    rule_version = db.Column(db.String(20))
    weather_temp = db.Column(db.Float)
    weather_humidity = db.Column(db.Float)
    weather_rainfall = db.Column(db.Float)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)


def record_to_dict(r):
    """Serialise a SoilRecord and its Prescription for the API response."""
    p = r.prescription
    return {
        'id': r.id, 'crop_name': r.crop_name, 'ph': r.ph,
        'nitrogen': r.nitrogen, 'phosphorus': r.phosphorus, 'potassium': r.potassium,
        'location_type': r.location_type, 'recorded_at': r.recorded_at.isoformat(),
        'prescription': {
            'fertilizer_name': p.fertilizer_name, 'quantity': p.quantity, 'unit': p.unit,
            'method': p.method, 'frequency': p.frequency, 'note': p.note,
            'safety_note': p.safety_note, 'rule_version': p.rule_version,
            'weather_temp': p.weather_temp, 'weather_humidity': p.weather_humidity,
            'weather_rainfall': p.weather_rainfall,
        } if p else None,
    }
