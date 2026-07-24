import math


VALID_PROGRAMME_TYPES = {"Bachelor", "Diploma", "Bachelor Night"}
VALID_NTA_LEVELS = {4, 5, 6, 7, 8}


def clean_text(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def normalize_programme_type(value):
    text = clean_text(value)
    if not text:
        raise ValueError("Programme type is required")
    lowered = text.lower()
    mapping = {
        "bachelor": "Bachelor",
        "degree": "Bachelor",
        "diploma": "Diploma",
        "bachelor night": "Bachelor Night",
        "night bachelor": "Bachelor Night",
        "evening bachelor": "Bachelor Night",
    }
    if lowered not in mapping:
        raise ValueError("Unsupported programme type: {}".format(text))
    return mapping[lowered]


def parse_nta_level(value):
    if value is None:
        raise ValueError("NTA level is required")
    text = str(value).strip().lower().replace("nta", "").replace("level", "").strip()
    try:
        parsed = int(float(text))
    except ValueError as exc:
        raise ValueError("Invalid NTA level: {}".format(value)) from exc
    if parsed not in VALID_NTA_LEVELS:
        raise ValueError("NTA level must be one of {}".format(sorted(VALID_NTA_LEVELS)))
    return parsed


def split_multi_value(value):
    text = clean_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def normalize_column_name(value):
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")
