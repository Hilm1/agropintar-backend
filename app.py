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

# The Gemini key is read from the environment. It is NEVER written in the code.
# Set it locally with:  export GEMINI_API_KEY="your_key_here"
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_URL     = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

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
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    crop_name     = db.Column(db.String(100), nullable=False)
    ph            = db.Column(db.Float, nullable=False)
    nitrogen      = db.Column(db.Float, nullable=False)
    phosphorus    = db.Column(db.Float, nullable=False)
    potassium     = db.Column(db.Float, nullable=False)
    location_type = db.Column(db.String(10), default='outdoor')
    recorded_at   = db.Column(db.DateTime, default=datetime.utcnow)
    prescription  = db.relationship('Prescription', backref='record', uselist=False, cascade='all, delete-orphan')

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
    weather_rainfall = db.Column(db.Float)
    generated_at     = db.Column(db.DateTime, default=datetime.utcnow)

CROPS = [
    {"id":1,"name":"Chili","emoji":"\U0001F336"},{"id":2,"name":"Tomato","emoji":"\U0001F345"},
    {"id":3,"name":"Kangkung","emoji":"\U0001F96C"},{"id":4,"name":"Cucumber","emoji":"\U0001F952"},
    {"id":5,"name":"Bayam","emoji":"\U0001F33F"},{"id":6,"name":"Pandan","emoji":"\U0001F331"},
    {"id":7,"name":"Brinjal","emoji":"\U0001F346"},{"id":8,"name":"Okra","emoji":"\U0001F33F"},
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
FRUITING = {"chili","tomato","brinjal","okra","cucumber"}

def apply_weather(rec, weather, location_type):
    if location_type != 'outdoor':
        return rec
    rain = float(weather.get('rainfall', 0.0) or 0.0)
    temp = float(weather.get('temperature', 28.0) or 28.0)
    extra = []
    if rain >= 2.0:
        extra.append("Heavy rain is recent or expected, which can wash nitrogen out of the soil before your plant uses it. Delay applying until after the rain passes, or split the amount into two smaller applications a few days apart.")
    if temp >= 32.0:
        extra.append("It is very warm at the moment, so apply in the cooler early morning or evening and water lightly afterward to help the plant take up the nutrients.")
    if extra:
        rec = dict(rec)
        rec['note'] = (rec['note'] + " " + " ".join(extra)).strip()
    return rec

def get_prescription(soil, crop, weather, location_type='outdoor'):
    N = float(soil['nitrogen']); P = float(soil['phosphorus']); K = float(soil['potassium'])
    ph = float(soil['ph'])
    profile = CROP_PROFILES.get(crop.lower(), CROP_PROFILES['chili'])
    if ph < profile['pH'][0] - 0.3:
        rec = {"fertilizer_name":"Agricultural Lime","quantity":"20g","unit":"per pot",
               "method":"Mix evenly into the top 5cm of soil and water well. Re-test pH after 2 weeks.",
               "frequency":"Once, then re-test",
               "note":"Your soil pH of "+str(ph)+" is too acidic for "+crop+". Agricultural lime will gradually raise the pH into the ideal range, which makes the nutrients already in your soil available to the plant."}
        return apply_weather(rec, weather, location_type)
    if ph > profile['pH'][1] + 0.3:
        rec = {"fertilizer_name":"Sulphur Powder","quantity":"10g","unit":"per pot",
               "method":"Mix evenly into the top 3cm of soil and water well. Re-test pH after 2 weeks.",
               "frequency":"Once, then re-test",
               "note":"Your soil pH of "+str(ph)+" is too alkaline for "+crop+". Sulphur powder will gradually lower the pH into the ideal range."}
        return apply_weather(rec, weather, location_type)
    if N < profile['N'][0]:
        rec = {"fertilizer_name":"Urea (46-0-0)","quantity":"5g","unit":"per plant",
               "method":"Sprinkle evenly around the base of the plant, 5 to 10cm from the stem. Water lightly after application.",
               "frequency":"Every 14 days",
               "note":"Your soil nitrogen ("+format(N,'.0f')+" mg/kg) is below the healthy range for "+crop+", which often shows as pale or yellowing leaves. Urea gives a fast nitrogen boost to promote healthy leaf and stem growth."}
        return apply_weather(rec, weather, location_type)
    if P < profile['P'][0]:
        rec = {"fertilizer_name":"Single Superphosphate (0-20-0)","quantity":"8g","unit":"per plant",
               "method":"Mix into the top 5cm of soil around the plant base. Water well after application.",
               "frequency":"Every 21 days",
               "note":"Your soil phosphorus ("+format(P,'.0f')+" mg/kg) is below the healthy range for "+crop+". Superphosphate strengthens the root system and improves the plant's ability to absorb water and nutrients."}
        return apply_weather(rec, weather, location_type)
    if K < profile['K'][0]:
        rec = {"fertilizer_name":"Muriate of Potash (0-0-60)","quantity":"4g","unit":"per plant",
               "method":"Dissolve in water at 1g per litre and apply as a liquid feed around the root zone.",
               "frequency":"Every 14 days",
               "note":"Your soil potassium ("+format(K,'.0f')+" mg/kg) is below the healthy range for "+crop+". Potash improves fruit quality, disease resistance, and the overall vigour of the plant."}
        return apply_weather(rec, weather, location_type)
    if N > profile['N'][1]:
        detail = " In fruiting crops, too much nitrogen causes leafy growth at the expense of fruit." if crop.lower() in FRUITING else ""
        rec = {"fertilizer_name":"No nitrogen fertilizer needed","quantity":"0g","unit":"",
               "method":"Do not add nitrogen fertilizer for now. Water normally and re-test the soil in about 3 weeks.",
               "frequency":"Hold and re-test",
               "note":"Your soil nitrogen ("+format(N,'.0f')+" mg/kg) is above the healthy range for "+crop+", so adding more would do harm rather than good."+detail+" Hold off on nitrogen and let the plant draw the level down."}
        return apply_weather(rec, weather, location_type)
    if P > profile['P'][1] or K > profile['K'][1]:
        rec = {"fertilizer_name":"No fertilizer needed","quantity":"0g","unit":"",
               "method":"Do not add fertilizer for now. Water normally and re-test the soil in about 3 weeks.",
               "frequency":"Hold and re-test",
               "note":"One or more nutrient levels in your soil are above the healthy range for "+crop+". Adding more fertilizer now could unbalance the soil, so hold off and re-test soon."}
        return apply_weather(rec, weather, location_type)
    rec = {"fertilizer_name":"NPK 15-15-15 (Balanced)","quantity":"6g","unit":"per plant",
           "method":"Sprinkle evenly around the base, 5 to 10cm from the stem. Water thoroughly after application.",
           "frequency":"Every 14 days",
           "note":"Your soil nutrient levels are within the healthy range for "+crop+". A light balanced NPK feed will maintain steady, healthy growth."}
    return apply_weather(rec, weather, location_type)

def llm_explain(rec, crop, soil, location_type):
    if not GEMINI_API_KEY:
        return rec['note']
    try:
        prompt = (
            "You are a friendly gardening assistant for Malaysian home gardeners. "
            "A rule-based system has already decided the fertilizer recommendation below. "
            "You must NOT change any product name, quantity, unit, or frequency. "
            "Only re-explain the recommendation in warm, simple language for a beginner, in 2 to 3 short sentences. "
            "Do not invent any new numbers.\n\n"
            "Crop: "+crop+"\n"
            "Soil readings: nitrogen "+format(float(soil['nitrogen']),'.0f')+" mg/kg, phosphorus "+format(float(soil['phosphorus']),'.0f')+" mg/kg, "
            "potassium "+format(float(soil['potassium']),'.0f')+" mg/kg, pH "+str(float(soil['ph']))+"\n"
            "Growing location: "+location_type+"\n"
            "Recommendation: apply "+str(rec['quantity'])+" "+str(rec['unit'])+" of "+rec['fertilizer_name']+", "+rec['frequency']+".\n"
            "Method: "+rec['method']+"\n"
            "Background reason: "+rec['note']
        )
        r = requests.post(GEMINI_URL+"?key="+GEMINI_API_KEY,
                          json={"contents":[{"parts":[{"text":prompt}]}]}, timeout=8)
        if r.status_code == 200:
            text = r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            if text:
                return text
    except Exception:
        pass
    return rec['note']

def get_weather(lat, lon):
    try:
        url=("https://api.open-meteo.com/v1/forecast?latitude="+str(lat)+"&longitude="+str(lon)+
             "&current=temperature_2m,relative_humidity_2m,precipitation&timezone=Asia/Kuala_Lumpur")
        r=requests.get(url,timeout=5)
        if r.status_code==200:
            c=r.json().get('current',{})
            return {'temperature':c.get('temperature_2m',28.0),'humidity':c.get('relative_humidity_2m',75.0),'rainfall':c.get('precipitation',0.0)}
    except: pass
    return {'temperature':28.0,'humidity':75.0,'rainfall':0.0}

def rec_to_dict(r):
    p=r.prescription
    return {'id':r.id,'crop_name':r.crop_name,'ph':r.ph,'nitrogen':r.nitrogen,
            'phosphorus':r.phosphorus,'potassium':r.potassium,'location_type':r.location_type,
            'recorded_at':r.recorded_at.isoformat(),
            'prescription':{'fertilizer_name':p.fertilizer_name,'quantity':p.quantity,'unit':p.unit,
                            'method':p.method,'frequency':p.frequency,'note':p.note,
                            'weather_temp':p.weather_temp,'weather_humidity':p.weather_humidity,
                            'weather_rainfall':p.weather_rainfall} if p else None}

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

@app.route('/api/crops',methods=['GET'])
def get_crops(): return jsonify(CROPS),200

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
    loc_type=d.get('location_type','outdoor')
    r=SoilRecord(user_id=uid,crop_name=d['crop_name'],ph=float(d['ph']),
                 nitrogen=float(d['nitrogen']),phosphorus=float(d['phosphorus']),potassium=float(d['potassium']),
                 location_type=loc_type)
    db.session.add(r); db.session.flush()
    w=get_weather(user.lat,user.lon)
    rx=get_prescription(d,d['crop_name'],w,loc_type)
    friendly_note=llm_explain(rx,d['crop_name'],d,loc_type)
    p=Prescription(record_id=r.id,fertilizer_name=rx['fertilizer_name'],quantity=rx['quantity'],
                   unit=rx['unit'],method=rx['method'],frequency=rx['frequency'],note=friendly_note,
                   weather_temp=w['temperature'],weather_humidity=w['humidity'],weather_rainfall=w['rainfall'])
    db.session.add(p); db.session.commit()
    return jsonify(rec_to_dict(r)),201

@app.route('/api/records/<int:rid>',methods=['PUT'])
@jwt_required()
def update_record(rid):
    uid=int(get_jwt_identity()); user=User.query.get(uid)
    r=SoilRecord.query.filter_by(id=rid,user_id=uid).first()
    if not r: return jsonify({'error':'Not found.'}),404
    d=request.get_json()
    if 'crop_name'     in d: r.crop_name    =d['crop_name']
    if 'ph'            in d: r.ph           =float(d['ph'])
    if 'nitrogen'      in d: r.nitrogen     =float(d['nitrogen'])
    if 'phosphorus'    in d: r.phosphorus   =float(d['phosphorus'])
    if 'potassium'     in d: r.potassium    =float(d['potassium'])
    if 'location_type' in d: r.location_type=d['location_type']
    w=get_weather(user.lat,user.lon)
    soil={'ph':r.ph,'nitrogen':r.nitrogen,'phosphorus':r.phosphorus,'potassium':r.potassium}
    rx=get_prescription(soil,r.crop_name,w,r.location_type)
    friendly_note=llm_explain(rx,r.crop_name,soil,r.location_type)
    p=r.prescription
    if p:
        p.fertilizer_name=rx['fertilizer_name']; p.quantity=rx['quantity']; p.unit=rx['unit']
        p.method=rx['method']; p.frequency=rx['frequency']; p.note=friendly_note
        p.weather_temp=w['temperature']; p.weather_humidity=w['humidity']; p.weather_rainfall=w['rainfall']
        p.generated_at=datetime.utcnow()
    db.session.commit(); return jsonify({'message':'Updated.'}),200

@app.route('/api/records/<int:rid>',methods=['DELETE'])
@jwt_required()
def delete_record(rid):
    r=SoilRecord.query.filter_by(id=rid,user_id=int(get_jwt_identity())).first()
    if not r: return jsonify({'error':'Not found.'}),404
    db.session.delete(r); db.session.commit(); return jsonify({'message':'Deleted.'}),200

@app.route('/api/chat',methods=['POST'])
@jwt_required()
def chat():
    d=request.get_json()
    rid=d.get('record_id'); question=(d.get('question') or '').strip()
    history=d.get('history',[])
    if not question: return jsonify({'error':'Question is required.'}),400
    r=SoilRecord.query.filter_by(id=rid,user_id=int(get_jwt_identity())).first()
    if not r or not r.prescription: return jsonify({'error':'Record not found.'}),404
    p=r.prescription
    if not GEMINI_API_KEY:
        return jsonify({'answer':"The chat assistant is not available right now, but the recommendation shown above still applies to your plant."}),200
    try:
        context=(
            "You are a friendly gardening assistant for Malaysian home gardeners. "
            "For the user's "+r.crop_name+", a rule-based system recommended: apply "+str(p.quantity)+" "+str(p.unit)+" of "+
            str(p.fertilizer_name)+", "+str(p.frequency)+". Method: "+str(p.method)+". "
            "You must NOT change the fertilizer, quantity, unit, or frequency. If the user asks for a different amount, "
            "explain that you can only advise on this recommendation and suggest they re-test their soil for a fresh one. "
            "If they describe a problem that is not about soil nutrients, such as pests or disease, gently note this tool "
            "only advises on fertilizer and suggest they check with a local nursery. Answer in 2 to 4 short sentences."
        )
        contents=[{"role":"user","parts":[{"text":context}]}]
        for m in history[-6:]:
            role="model" if m.get('role')=='assistant' else "user"
            contents.append({"role":role,"parts":[{"text":m.get('text','')}]})
        contents.append({"role":"user","parts":[{"text":question}]})
        resp=requests.post(GEMINI_URL+"?key="+GEMINI_API_KEY,json={"contents":contents},timeout=10)
        if resp.status_code==200:
            answer=resp.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            if answer: return jsonify({'answer':answer}),200
    except Exception:
        pass
    return jsonify({'answer':"Sorry, I could not process that just now. Please try again in a moment."}),200

with app.app_context():
    db.create_all()

if __name__=='__main__':
    port=int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0',port=port,debug=False)
