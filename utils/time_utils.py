from datetime import date, datetime, time, timedelta


SESSION_DEFAULT_START_TIMES = {
    "Morning": "08:00",
    "Afternoon": "13:00",
    "Night": "18:00",
}


def parse_time(value):
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time().replace(second=0, microsecond=0)
    if value is None:
        raise ValueError("Time is required")

    text = str(value).strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError("Invalid time format. Use HH:MM, for example 08:00.")


def time_to_minutes(value):
    parsed = parse_time(value)
    return parsed.hour * 60 + parsed.minute


def minutes_to_time(minutes):
    minutes = int(minutes) % (24 * 60)
    return "{:02d}:{:02d}".format(minutes // 60, minutes % 60)


def calculate_end_time(start_time, duration_minutes):
    if duration_minutes is None:
        raise ValueError("Duration is required")
    return minutes_to_time(time_to_minutes(start_time) + int(duration_minutes))


def time_ranges_overlap(existing_start, existing_end, new_start, new_end):
    existing_start_minutes = time_to_minutes(existing_start)
    existing_end_minutes = time_to_minutes(existing_end)
    new_start_minutes = time_to_minutes(new_start)
    new_end_minutes = time_to_minutes(new_end)
    return existing_start_minutes < new_end_minutes and new_start_minutes < existing_end_minutes


def normalize_session_name(value):
    if not value:
        raise ValueError("Session is required")
    text = str(value).strip().lower()
    mapping = {
        "morning": "Morning",
        "am": "Morning",
        "afternoon": "Afternoon",
        "pm": "Afternoon",
        "night": "Night",
        "evening": "Night",
    }
    if text not in mapping:
        raise ValueError("Unsupported session. Use Morning, Afternoon, or Night.")
    return mapping[text]


def default_start_time_for_session(session_name):
    return SESSION_DEFAULT_START_TIMES[normalize_session_name(session_name)]


def normalize_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        raise ValueError("Date is required")

    if isinstance(value, (int, float)):
        if value > 10000000000:
            return datetime.fromtimestamp(value / 1000.0).date().isoformat()
        if value > 1000000000:
            return datetime.fromtimestamp(value).date().isoformat()
        excel_epoch = datetime(1899, 12, 30)
        return (excel_epoch + timedelta(days=float(value))).date().isoformat()

    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError("Invalid date format. Use YYYY-MM-DD.")


def display_date(value):
    normalized = normalize_date(value)
    return datetime.strptime(normalized, "%Y-%m-%d").strftime("%d-%m-%Y")


def session_code(date_value, session_name, programme_type):
    normalized_date = normalize_date(date_value)
    normalized_session = normalize_session_name(session_name).upper()
    normalized_programme = str(programme_type or "GENERAL").strip().upper().replace(" ", "-")
    return "{}-{}-{}".format(normalized_date, normalized_session, normalized_programme)
