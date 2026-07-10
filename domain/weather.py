"""Retrieval of local weather from the Open-Meteo service."""
import requests

DEFAULTS = {'temperature': 28.0, 'humidity': 75.0, 'rainfall': 0.0}


def get_weather(lat, lon):
    """Fetch current weather. Falls back to sensible defaults if unavailable."""
    try:
        url = ("https://api.open-meteo.com/v1/forecast"
               "?latitude=" + str(lat) + "&longitude=" + str(lon) +
               "&current=temperature_2m,relative_humidity_2m,precipitation"
               "&timezone=Asia/Kuala_Lumpur")
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            c = r.json().get('current', {})
            return {
                'temperature': c.get('temperature_2m', DEFAULTS['temperature']),
                'humidity': c.get('relative_humidity_2m', DEFAULTS['humidity']),
                'rainfall': c.get('precipitation', DEFAULTS['rainfall']),
            }
    except Exception:
        pass
    return dict(DEFAULTS)
