"""Chat route for grounded follow-up questions about a recommendation."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from core.models import SoilRecord
from domain import advisory

chat_bp = Blueprint('chat', __name__, url_prefix='/api')


@chat_bp.route('/chat', methods=['POST'])
@jwt_required()
def chat():
    d = request.get_json()
    rid = d.get('record_id')
    question = (d.get('question') or '').strip()
    history = d.get('history', [])
    if not question:
        return jsonify({'error': 'Question is required.'}), 400

    r = SoilRecord.query.filter_by(id=rid, user_id=int(get_jwt_identity())).first()
    if not r or not r.prescription:
        return jsonify({'error': 'Record not found.'}), 404

    answer = advisory.answer_question(r.prescription, r.crop_name, question, history)
    return jsonify({'answer': answer}), 200
