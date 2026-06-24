from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import requests, os, numpy as np

app = Flask(__name__)
CORS(app, origins="*")

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///agronomist.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET', 'agropintar-secret-2025')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=7)

db     = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt    = JWTManager(app)

# ── Models ──────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = 'users'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    location   = db.Column(db.String(100), default='Kuala Lumpur')
    lat        = db.Column(db.Float, default=3.1390)
    lon        = db.Column(db.Float, default=101.6869)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    records    = db.relationship('SoilRecord', backref='user', lazy=True, cascade='all, delete-orphan')

class SoilRecord(db.Model):
    __tablename__ = 'soil_records'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    crop_name   = db.Column(db.String(100), nullable=False)
    ph          = db.Column(db.Float, nullable=False)
    nitrogen    = db.Column(db.String(20), nullable=False)
    phosphorus  = db.Column(db.String(20), nullable=False)
    potassium   = db.Column(db.String(20), nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    prescription = db.relationship('Prescription', backref='record', uselist=False, cascade='all, delete-orphan')

class Prescription(db.Model):
    __tablename__ = 'prescriptions'
    id               = db.Column(db.Integer, primary_key=True)
    record_id        = db.Column(db.Integer, db.ForeignKey('soil_records.id'), nullable=False)
    fertilizer_name  = db.Column(db.String(100))
    quantity         = db.Column(db.String(50))
    unit             = db.Column(db.String(30))
    method           = db.Column(db.String(300))
    frequency        = db.Column(db.String(100))
    note             = db.Column(db.Text)
    weather_temp     = db.Column(db.Float)
    weather_humidity = db.Column(db.Float)
    generated_at     = db.Column(db.DateTime, default=datetime.utcnow)

# ── Crops ────────────────────────────────────────────────────
CROPS = [
    {"id":1,"name":"Chili","emoji":"🌶"},{"id":2,"name":"Tomato","emoji":"🍅"},
    {"id":3,"name":"Kangkung","emoji":"🥬"},{"id":4,"name":"Cucumber","emoji":"🥒"},
    {"id":5,"name":"Bayam","emoji":"🌿"},{"id":6,"name":"Pandan","emoji":"🌱"},
    {"id":7,"name":"Brinjal","emoji":"🍆"},{"id":8,"name":"Okra","emoji":"🌿"},
]

CROP_PROFILES = {
    "chili":    {"N":(60,90), "P":(40,70), "K":(50,80),  "pH":(6.0,7.0)},
    "tomato":   {"N":(80,120),"P":(50,80), "K":(80,120), "pH":(6.0,6.8)},
    "kangkung": {"N":(50,80), "P":(30,55), "K":(40,60),  "pH":(5.5,7.0)},
    "cucumber": {"N":(60,100),"P":(40,65), "K":(60,90),  "pH":(6.0,7.0)},
    "bayam":    {"N":(40,70), "P":(30,50), "K":(35,55),  "pH":(5.5,6.5)},
    "pandan":   {"N":(30,60), "P":(25,45), "K":(30,50),  "pH":(5.5,6.5)},
    "brinjal":  {"N":(70,110),"P":(45,75), "K":(70,100), "pH":(5.5,6.8)},
    "okra":     {"N":(50,80), "P":(35,60), "K":(50,75),  "pH":(6.0,7.5)},
}

NPK_NUM = {"low":(10,35),"medium":(40,70),"high":(75,130)}

def npk_val(level): r=NPK_NUM.get(level.lower(),(40,70)); return (r[0]+r[1])/2

def get_prescription(soil, crop, weather):
    N = npk_val(soil['nitrogen']); P = npk_val(soil['phosphorus']); K = npk_val(soil['potassium'])
    ph = float(soil['ph']); profile = CROP_PROFILES.get(crop.lower(), CROP_PROFILES['chili'])
    def in_range(v,lo,hi): return lo<=v<=hi
    def below(v,lo): return v<lo
    N_ok=in_range(N,*profile['N']); P_ok=in_range(P,*profile['P'])
    K_ok=in_range(K,*profile['K']); pH_ok=in_range(ph,*profile['pH'])
    # pH priority first
    if ph < profile['pH'][0] - 0.3:
        return {"fertilizer_name":"Agricultural Lime","quantity":"20g","unit":"per pot",
                "method":"Mix evenly into the top 5cm of soil and water well. Re-test pH after 2 weeks.",
                "frequency":"Once, then re-test","note":f"Your soil pH of {ph} is too acidic for {crop}. Agricultural lime will gradually raise pH to the optimal range, making nutrients more available to your plant."}
    if ph > profile['pH'][1] + 0.3:
        return {"fertilizer_name":"Sulphur Powder","quantity":"10g","unit":"per pot",
                "method":"Mix evenly into the top 3cm of soil and water well. Re-test pH after 2 weeks.",
                "frequency":"Once, then re-test","note":f"Your soil pH of {ph} is too alkaline for {crop}. Sulphur powder will gradually lower pH to the optimal range."}
    # NPK deficiency
    if below(N,profile['N'][0]):
        return {"fertilizer_name":"Urea (46-0-0)","quantity":"5g","unit":"per plant",
                "method":"Sprinkle evenly around the base of the plant, 5 to 10cm from the stem. Water lightly after application.",
                "frequency":"Every 14 days","note":f"Your soil nitrogen is low, which is likely why your {crop} may be showing pale or yellowing leaves. Urea will deliver a fast-acting nitrogen boost to promote healthy leaf and stem growth."}
    if below(P,profile['P'][0]):
        return {"fertilizer_name":"Single Superphosphate (0-20-0)","quantity":"8g","unit":"per plant",
                "method":"Mix into the top 5cm of soil around the plant base. Water well after application.",
                "frequency":"Every 21 days","note":f"Your soil phosphorus is low. Superphosphate will strengthen the root system of your {crop} and improve its ability to absorb water and other nutrients from the soil."}
    if below(K,profile['K'][0]):
        return {"fertilizer_name":"Muriate of Potash (0-0-60)","quantity":"4g","unit":"per plant",
                "method":"Dissolve in water at 1g per litre and apply as liquid feed around the root zone.",
                "frequency":"Every 14 days","note":f"Your soil potassium is low. Potash will improve fruit quality, strengthen disease resistance, and improve the overall vigour of your {crop}."}
    # All in range
    return {"fertilizer_name":"NPK 15-15-15 (Balanced)","quantity":"6g","unit":"per plant",
            "method":"Sprinkle evenly around the base, 5 to 10cm from the stem. Water thoroughly after application.",
            "frequency":"Every 14 days","note":f"Your soil nutrient levels are reasonably balanced for {crop}. A balanced NPK fertilizer will maintain steady, healthy growth throughout the growing season."}

def get_weather(lat, lon):
    try:
        url=(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
             f"&current=temperature_2m,relative_humidity_2m,precipitation&timezone=Asia/Kuala_Lumpur")
        r=requests.get(url,timeout=5)
        if r.status_code==200:
            c=r.json().get('current',{})
            return {'temperature':c.get('temperature_2m',28.0),'humidity':c.get('relative_humidity_2m',75.0),'rainfall':c.get('precipitation',0.0)}
    except: pass
    return {'temperature':28.0,'humidity':75.0,'rainfall':0.0}

def rec_to_dict(r):
    p=r.prescription
    return {'id':r.id,'crop_name':r.crop_name,'ph':r.ph,'nitrogen':r.nitrogen,
            'phosphorus':r.phosphorus,'potassium':r.potassium,'recorded_at':r.recorded_at.isoformat(),
            'prescription':{'fertilizer_name':p.fertilizer_name,'quantity':p.quantity,'unit':p.unit,
                            'method':p.method,'frequency':p.frequency,'note':p.note,
                            'weather_temp':p.weather_temp,'weather_humidity':p.weather_humidity} if p else None}

# ── Auth ─────────────────────────────────────────────────────
@app.route('/api/auth/register',methods=['POST'])
def register():
    d=request.get_json()
    if not all(k in d for k in ['name','email','password']): return jsonify({'error':'Name, email and password are required.'}),400
    if User.query.filter_by(email=d['email']).first(): return jsonify({'error':'An account with this email already exists.'}),409
    u=User(name=d['name'],email=d['email'],password=bcrypt.generate_password_hash(d['password']).decode(),
           location=d.get('location','Kuala Lumpur'),lat=d.get('lat',3.1390),lon=d.get('lon',101.6869))
    db.session.add(u); db.session.commit()
    return jsonify({'token':create_access_token(identity=str(u.id)),'user':{'id':u.id,'name':u.name,'email':u.email,'location':u.location}}),201

@app.route('/api/auth/login',methods=['POST'])
def login():
    d=request.get_json(); u=User.query.filter_by(email=d.get('email','')).first()
    if not u or not bcrypt.check_password_hash(u.password,d.get('password','')): return jsonify({'error':'Invalid email or password.'}),401
    return jsonify({'token':create_access_token(identity=str(u.id)),'user':{'id':u.id,'name':u.name,'email':u.email,'location':u.location}}),200

@app.route('/api/auth/me',methods=['GET'])
@jwt_required()
def me():
    u=User.query.get(int(get_jwt_identity()))
    if not u: return jsonify({'error':'Not found.'}),404
    return jsonify({'id':u.id,'name':u.name,'email':u.email,'location':u.location}),200

@app.route('/api/auth/update',methods=['PUT'])
@jwt_required()
def update_profile():
    u=User.query.get(int(get_jwt_identity())); d=request.get_json()
    if 'name' in d: u.name=d['name']
    if 'location' in d: u.location=d['location']
    db.session.commit(); return jsonify({'message':'Profile updated.'}),200

# ── Crops ────────────────────────────────────────────────────
@app.route('/api/crops',methods=['GET'])
def get_crops(): return jsonify(CROPS),200

# ── Records CRUD ─────────────────────────────────────────────
@app.route('/api/records',methods=['GET'])
@jwt_required()
def get_records():
    uid=int(get_jwt_identity())
    records=SoilRecord.query.filter_by(user_id=uid).order_by(SoilRecord.recorded_at.desc()).all()
    return jsonify([rec_to_dict(r) for r in records]),200

@app.route('/api/records/<int:rid>',methods=['GET'])
@jwt_required()
def get_record(rid):
    r=SoilRecord.query.filter_by(id=rid,user_id=int(get_jwt_identity())).first()
    if not r: return jsonify({'error':'Not found.'}),404
    return jsonify(rec_to_dict(r)),200

@app.route('/api/records',methods=['POST'])
@jwt_required()
def create_record():
    uid=int(get_jwt_identity()); user=User.query.get(uid); d=request.get_json()
    if not all(k in d for k in ['crop_name','ph','nitrogen','phosphorus','potassium']): return jsonify({'error':'All fields required.'}),400
    r=SoilRecord(user_id=uid,crop_name=d['crop_name'],ph=float(d['ph']),
                 nitrogen=d['nitrogen'],phosphorus=d['phosphorus'],potassium=d['potassium'])
    db.session.add(r); db.session.flush()
    w=get_weather(user.lat,user.lon); rx=get_prescription(d,d['crop_name'],w)
    p=Prescription(record_id=r.id,fertilizer_name=rx['fertilizer_name'],quantity=rx['quantity'],
                   unit=rx['unit'],method=rx['method'],frequency=rx['frequency'],note=rx['note'],
                   weather_temp=w['temperature'],weather_humidity=w['humidity'])
    db.session.add(p); db.session.commit()
    return jsonify(rec_to_dict(r)),201

@app.route('/api/records/<int:rid>',methods=['PUT'])
@jwt_required()
def update_record(rid):
    uid=int(get_jwt_identity()); user=User.query.get(uid)
    r=SoilRecord.query.filter_by(id=rid,user_id=uid).first()
    if not r: return jsonify({'error':'Not found.'}),404
    d=request.get_json()
    if 'crop_name'  in d: r.crop_name  =d['crop_name']
    if 'ph'         in d: r.ph         =float(d['ph'])
    if 'nitrogen'   in d: r.nitrogen   =d['nitrogen']
    if 'phosphorus' in d: r.phosphorus =d['phosphorus']
    if 'potassium'  in d: r.potassium  =d['potassium']
    w=get_weather(user.lat,user.lon)
    rx=get_prescription({'ph':r.ph,'nitrogen':r.nitrogen,'phosphorus':r.phosphorus,'potassium':r.potassium},r.crop_name,w)
    p=r.prescription
    if p:
        p.fertilizer_name=rx['fertilizer_name']; p.quantity=rx['quantity']; p.unit=rx['unit']
        p.method=rx['method']; p.frequency=rx['frequency']; p.note=rx['note']
        p.weather_temp=w['temperature']; p.weather_humidity=w['humidity']; p.generated_at=datetime.utcnow()
    db.session.commit(); return jsonify({'message':'Updated.'}),200

@app.route('/api/records/<int:rid>',methods=['DELETE'])
@jwt_required()
def delete_record(rid):
    r=SoilRecord.query.filter_by(id=rid,user_id=int(get_jwt_identity())).first()
    if not r: return jsonify({'error':'Not found.'}),404
    db.session.delete(r); db.session.commit(); return jsonify({'message':'Deleted.'}),200

with app.app_context():
    db.create_all()

if __name__=='__main__':
    port=int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0',port=port,debug=False)
