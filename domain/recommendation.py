"""Rule-based fertilizer recommendation engine.

The recommendation is decided entirely by the rules in this module.
Rules are applied in order of agronomic priority:
  1. Soil pH, because pH governs whether nutrients are available at all.
  2. Nutrient deficiency, correcting whichever nutrient is below range.
  3. Nutrient excess, advising the gardener to withhold rather than add more.
  4. Balanced maintenance, when all levels are healthy.
A weather adjustment is then applied, but only for plants grown outdoors.
"""
from domain.crops import CROP_PROFILES, FRUITING

# Version of the rule set. Stored with every recommendation so that any past
# recommendation can be traced back to the exact rules that produced it.
RULE_VERSION = "1.0"

# Safety guidance attached to each fertilizer product. Shown to the user alongside
# the recommendation, since fertilizer is a chemical applied to edible crops.
SAFETY_NOTES = {
    "Agricultural Lime": "Wear gloves and avoid breathing in the dust. Keep away from children and pets until it is mixed into the soil and watered in.",
    "Sulphur Powder": "Wear gloves and a mask when handling. Avoid applying on windy days, and keep away from children and pets.",
    "Urea (46-0-0)": "Do not let urea touch the leaves or stem, as it can burn the plant. Wash your hands after handling, and store it out of reach of children.",
    "Single Superphosphate (0-20-0)": "Wear gloves when handling. Avoid over-applying, as excess phosphorus can wash into drains and waterways.",
    "Muriate of Potash (0-0-60)": "Wear gloves when handling. Do not exceed the recommended amount, as too much can harm the roots.",
    "NPK 15-15-15 (Balanced)": "Keep the granules away from the plant stem to avoid burning it. Wash your hands after handling and store out of reach of children.",
    "No nitrogen fertilizer needed": "No fertilizer is being applied, so there is nothing to handle. Continue watering as normal.",
    "No fertilizer needed": "No fertilizer is being applied, so there is nothing to handle. Continue watering as normal.",
}


def get_safety_note(fertilizer_name):
    """Return the safety guidance for a fertilizer, with a general fallback."""
    return SAFETY_NOTES.get(
        fertilizer_name,
        "Wear gloves when handling fertilizer, wash your hands afterwards, and store it out of reach of children and pets."
    )


def apply_weather(rec, weather, location_type):
    """Adjust advice for local weather. Indoor plants are sheltered, so skipped."""
    if location_type != 'outdoor':
        return rec
    rain = float(weather.get('rainfall', 0.0) or 0.0)
    temp = float(weather.get('temperature', 28.0) or 28.0)
    extra = []
    if rain >= 2.0:
        extra.append("Heavy rain is recent or expected, which can wash nitrogen out of "
                     "the soil before your plant uses it. Delay applying until after the "
                     "rain passes, or split the amount into two smaller applications a "
                     "few days apart.")
    if temp >= 32.0:
        extra.append("It is very warm at the moment, so apply in the cooler early morning "
                     "or evening and water lightly afterward to help the plant take up "
                     "the nutrients.")
    if extra:
        rec = dict(rec)
        rec['note'] = (rec['note'] + " " + " ".join(extra)).strip()
    return rec


def get_prescription(soil, crop, weather, location_type='outdoor'):
    """Return the fertilizer recommendation for a soil reading and crop."""
    N = float(soil['nitrogen'])
    P = float(soil['phosphorus'])
    K = float(soil['potassium'])
    ph = float(soil['ph'])
    profile = CROP_PROFILES.get(crop.lower(), CROP_PROFILES['chili'])

    # Stage 1 - soil pH takes priority.
    if ph < profile['pH'][0] - 0.3:
        return apply_weather({
            "fertilizer_name": "Agricultural Lime", "quantity": "20g", "unit": "per pot",
            "method": "Mix evenly into the top 5cm of soil and water well. Re-test pH after 2 weeks.",
            "frequency": "Once, then re-test",
            "note": "Your soil pH of " + str(ph) + " is too acidic for " + crop +
                    ". Agricultural lime will gradually raise the pH into the ideal range, "
                    "which makes the nutrients already in your soil available to the plant."
        }, weather, location_type)

    if ph > profile['pH'][1] + 0.3:
        return apply_weather({
            "fertilizer_name": "Sulphur Powder", "quantity": "10g", "unit": "per pot",
            "method": "Mix evenly into the top 3cm of soil and water well. Re-test pH after 2 weeks.",
            "frequency": "Once, then re-test",
            "note": "Your soil pH of " + str(ph) + " is too alkaline for " + crop +
                    ". Sulphur powder will gradually lower the pH into the ideal range."
        }, weather, location_type)

    # Stage 2 - nutrient deficiency.
    if N < profile['N'][0]:
        return apply_weather({
            "fertilizer_name": "Urea (46-0-0)", "quantity": "5g", "unit": "per plant",
            "method": "Sprinkle evenly around the base of the plant, 5 to 10cm from the stem. Water lightly after application.",
            "frequency": "Every 14 days",
            "note": "Your soil nitrogen (" + format(N, '.0f') + " mg/kg) is below the healthy range for " +
                    crop + ", which often shows as pale or yellowing leaves. Urea gives a fast "
                    "nitrogen boost to promote healthy leaf and stem growth."
        }, weather, location_type)

    if P < profile['P'][0]:
        return apply_weather({
            "fertilizer_name": "Single Superphosphate (0-20-0)", "quantity": "8g", "unit": "per plant",
            "method": "Mix into the top 5cm of soil around the plant base. Water well after application.",
            "frequency": "Every 21 days",
            "note": "Your soil phosphorus (" + format(P, '.0f') + " mg/kg) is below the healthy range for " +
                    crop + ". Superphosphate strengthens the root system and improves the plant's "
                    "ability to absorb water and nutrients."
        }, weather, location_type)

    if K < profile['K'][0]:
        return apply_weather({
            "fertilizer_name": "Muriate of Potash (0-0-60)", "quantity": "4g", "unit": "per plant",
            "method": "Dissolve in water at 1g per litre and apply as a liquid feed around the root zone.",
            "frequency": "Every 14 days",
            "note": "Your soil potassium (" + format(K, '.0f') + " mg/kg) is below the healthy range for " +
                    crop + ". Potash improves fruit quality, disease resistance, and the overall "
                    "vigour of the plant."
        }, weather, location_type)

    # Stage 3 - nutrient excess. Advise withholding rather than adding more.
    if N > profile['N'][1]:
        detail = (" In fruiting crops, too much nitrogen causes leafy growth at the expense of fruit."
                  if crop.lower() in FRUITING else "")
        return apply_weather({
            "fertilizer_name": "No nitrogen fertilizer needed", "quantity": "0g", "unit": "",
            "method": "Do not add nitrogen fertilizer for now. Water normally and re-test the soil in about 3 weeks.",
            "frequency": "Hold and re-test",
            "note": "Your soil nitrogen (" + format(N, '.0f') + " mg/kg) is above the healthy range for " +
                    crop + ", so adding more would do harm rather than good." + detail +
                    " Hold off on nitrogen and let the plant draw the level down."
        }, weather, location_type)

    if P > profile['P'][1] or K > profile['K'][1]:
        return apply_weather({
            "fertilizer_name": "No fertilizer needed", "quantity": "0g", "unit": "",
            "method": "Do not add fertilizer for now. Water normally and re-test the soil in about 3 weeks.",
            "frequency": "Hold and re-test",
            "note": "One or more nutrient levels in your soil are above the healthy range for " + crop +
                    ". Adding more fertilizer now could unbalance the soil, so hold off and re-test soon."
        }, weather, location_type)

    # Stage 4 - all nutrients within range.
    return apply_weather({
        "fertilizer_name": "NPK 15-15-15 (Balanced)", "quantity": "6g", "unit": "per plant",
        "method": "Sprinkle evenly around the base, 5 to 10cm from the stem. Water thoroughly after application.",
        "frequency": "Every 14 days",
        "note": "Your soil nutrient levels are within the healthy range for " + crop +
                ". A light balanced NPK feed will maintain steady, healthy growth."
    }, weather, location_type)
