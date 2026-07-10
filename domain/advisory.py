"""Language model advisory layer.

This layer never decides the recommendation. The rule engine fixes the
fertilizer, quantity, unit and frequency; the language model only explains
that recommendation in plain language and answers follow-up questions.
If the model is unavailable, the rule-based explanation is used instead.
"""
import requests
from core.config import Config


def _call_gemini(payload, timeout):
    """Post to the Gemini API and return the text, or None on any failure."""
    if not Config.GEMINI_API_KEY:
        return None
    try:
        r = requests.post(Config.GEMINI_URL + "?key=" + Config.GEMINI_API_KEY,
                          json=payload, timeout=timeout)
        if r.status_code == 200:
            text = r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            return text or None
    except Exception:
        pass
    return None


def explain(rec, crop, soil, location_type):
    """Rephrase the rule-based recommendation into warm, simple language."""
    prompt = (
        "You are a friendly gardening assistant for Malaysian home gardeners. "
        "A rule-based system has already decided the fertilizer recommendation below. "
        "You must NOT change any product name, quantity, unit, or frequency. "
        "Only re-explain the recommendation in warm, simple language for a beginner, "
        "in 2 to 3 short sentences. Do not invent any new numbers.\n\n"
        "Crop: " + crop + "\n"
        "Soil readings: nitrogen " + format(float(soil['nitrogen']), '.0f') + " mg/kg, "
        "phosphorus " + format(float(soil['phosphorus']), '.0f') + " mg/kg, "
        "potassium " + format(float(soil['potassium']), '.0f') + " mg/kg, "
        "pH " + str(float(soil['ph'])) + "\n"
        "Growing location: " + location_type + "\n"
        "Recommendation: apply " + str(rec['quantity']) + " " + str(rec['unit']) +
        " of " + rec['fertilizer_name'] + ", " + rec['frequency'] + ".\n"
        "Method: " + rec['method'] + "\n"
        "Background reason: " + rec['note']
    )
    text = _call_gemini({"contents": [{"parts": [{"text": prompt}]}]}, timeout=8)
    return text if text else rec['note']   # safe fallback


def answer_question(prescription, crop_name, question, history):
    """Answer a follow-up question, grounded in the fixed recommendation."""
    if not Config.GEMINI_API_KEY:
        return ("The chat assistant is not available right now, but the recommendation "
                "shown above still applies to your plant.")
    p = prescription
    context = (
        "You are a friendly gardening assistant for Malaysian home gardeners. "
        "For the user's " + crop_name + ", a rule-based system recommended: apply " +
        str(p.quantity) + " " + str(p.unit) + " of " + str(p.fertilizer_name) + ", " +
        str(p.frequency) + ". Method: " + str(p.method) + ". "
        "You must NOT change the fertilizer, quantity, unit, or frequency. If the user asks "
        "for a different amount, explain that you can only advise on this recommendation and "
        "suggest they re-test their soil for a fresh one. If they describe a problem that is "
        "not about soil nutrients, such as pests or disease, gently note this tool only advises "
        "on fertilizer and suggest they check with a local nursery. Answer in 2 to 4 short sentences."
    )
    contents = [{"role": "user", "parts": [{"text": context}]}]
    for m in (history or [])[-6:]:
        role = "model" if m.get('role') == 'assistant' else "user"
        contents.append({"role": role, "parts": [{"text": m.get('text', '')}]})
    contents.append({"role": "user", "parts": [{"text": question}]})

    text = _call_gemini({"contents": contents}, timeout=10)
    return text if text else "Sorry, I could not process that just now. Please try again in a moment."
