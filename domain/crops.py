"""Crop list and agronomic profiles.

Each profile defines the healthy range for nitrogen, phosphorus and potassium
in mg/kg, and the preferred soil pH range, compiled from agronomic guidance.
"""

CROPS = [
    {"id": 1, "name": "Chili",    "emoji": "\U0001F336"},
    {"id": 2, "name": "Tomato",   "emoji": "\U0001F345"},
    {"id": 3, "name": "Kangkung", "emoji": "\U0001F96C"},
    {"id": 4, "name": "Cucumber", "emoji": "\U0001F952"},
    {"id": 5, "name": "Bayam",    "emoji": "\U0001F33F"},
    {"id": 6, "name": "Pandan",   "emoji": "\U0001F331"},
    {"id": 7, "name": "Brinjal",  "emoji": "\U0001F346"},
    {"id": 8, "name": "Okra",     "emoji": "\U0001F33F"},
]

CROP_PROFILES = {
    "chili":    {"N": (60, 90),  "P": (40, 70), "K": (50, 80),  "pH": (6.0, 7.0)},
    "tomato":   {"N": (80, 120), "P": (50, 80), "K": (80, 120), "pH": (6.0, 6.8)},
    "kangkung": {"N": (50, 80),  "P": (30, 55), "K": (40, 60),  "pH": (5.5, 7.0)},
    "cucumber": {"N": (60, 100), "P": (40, 65), "K": (60, 90),  "pH": (6.0, 7.0)},
    "bayam":    {"N": (40, 70),  "P": (30, 50), "K": (35, 55),  "pH": (5.5, 6.5)},
    "pandan":   {"N": (30, 60),  "P": (25, 45), "K": (30, 50),  "pH": (5.5, 6.5)},
    "brinjal":  {"N": (70, 110), "P": (45, 75), "K": (70, 100), "pH": (5.5, 6.8)},
    "okra":     {"N": (50, 80),  "P": (35, 60), "K": (50, 75),  "pH": (6.0, 7.5)},
}

# Crops grown for their fruit, where excess nitrogen harms fruiting.
FRUITING = {"chili", "tomato", "brinjal", "okra", "cucumber"}
