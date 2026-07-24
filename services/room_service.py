from datetime import datetime


DEFAULT_ROOMS = [
    {"room_name": "ADM 303", "building": "Administration Block", "columns": 6, "rows": 7},
    {"room_name": "ADM 304", "building": "Administration Block", "columns": 8, "rows": 3},
    {"room_name": "ADM 305", "building": "Administration Block", "columns": 7, "rows": 3},
    {"room_name": "ADM 306", "building": "Administration Block", "columns": 7, "rows": 3},
    {"room_name": "ADM 307", "building": "Administration Block", "columns": 7, "rows": 3},
    {"room_name": "ADM 308", "building": "Administration Block", "columns": 7, "rows": 3},
    {"room_name": "ADM 309", "building": "Administration Block", "columns": 7, "rows": 3},
    {"room_name": "ADM 310", "building": "Administration Block", "columns": 7, "rows": 3},
    {"room_name": "ADM 311", "building": "Administration Block", "columns": 7, "rows": 3},
    {"room_name": "EAB 206", "building": "East Wing", "columns": 7, "rows": 3},
    {"room_name": "EAB 306", "building": "East Wing", "columns": 7, "rows": 3},
    {"room_name": "EAB 401", "building": "East Wing", "columns": 8, "rows": 3},
    {"room_name": "EAB 304", "building": "East Wing", "columns": 7, "rows": 3},
    {"room_name": "EAB 303", "building": "East Wing", "columns": 7, "rows": 3},
    {"room_name": "EAB 104", "building": "East Wing", "columns": 7, "rows": 3},
    {"room_name": "EAB 103", "building": "East Wing", "columns": 7, "rows": 3},
    {"room_name": "EAB 203", "building": "East Wing", "columns": 7, "rows": 3},
    {"room_name": "EAB 204", "building": "East Wing", "columns": 7, "rows": 3},
    {"room_name": "EAB 415", "building": "East Wing", "columns": 8, "rows": 15},
    {"room_name": "EAB 416", "building": "East Wing", "columns": 8, "rows": 14},
    {"room_name": "EAB 310", "building": "East Wing", "columns": 7, "rows": 3},
    {"room_name": "WAB 206", "building": "West Wing", "columns": 7, "rows": 3},
    {"room_name": "WAB 105", "building": "West Wing", "columns": 7, "rows": 3},
    {"room_name": "WAB 107", "building": "West Wing", "columns": 7, "rows": 3},
    {"room_name": "WAB 207", "building": "West Wing", "columns": 8, "rows": 3},
    {"room_name": "WAB 212", "building": "West Wing", "columns": 7, "rows": 3},
    {"room_name": "WAB 210", "building": "West Wing", "columns": 7, "rows": 3},
    {"room_name": "WAB 211", "building": "West Wing", "columns": 7, "rows": 3},
    {"room_name": "WAB 205", "building": "West Wing", "columns": 7, "rows": 3},
    {"room_name": "WAB 305", "building": "West Wing", "columns": 7, "rows": 3},
    {"room_name": "WAB 303", "building": "West Wing", "columns": 7, "rows": 3},
    {"room_name": "WAB 403", "building": "West Wing", "columns": 7, "rows": 3},
    {"room_name": "WAB 405", "building": "West Wing", "columns": 7, "rows": 3},
    {"room_name": "WAB 412", "building": "West Wing", "columns": 7, "rows": 3},
]


def room_code(room_name):
    return "".join(str(room_name).upper().split())


def validate_room_dimensions(rows, columns):
    rows = int(rows)
    columns = int(columns)
    if rows <= 0 or columns <= 0:
        raise ValueError("Room rows and columns must be positive")
    return rows, columns


def room_document(spec):
    rows, columns = validate_room_dimensions(spec["rows"], spec["columns"])
    return {
        "room_code": spec.get("room_code") or room_code(spec["room_name"]),
        "room_name": spec["room_name"],
        "building": spec.get("building"),
        "rows": rows,
        "columns": columns,
        "capacity": int(spec.get("capacity") or rows * columns),
        "is_active": bool(spec.get("is_active", True)),
    }


def seed_default_rooms(db):
    return ensure_rooms(db, DEFAULT_ROOMS)


def ensure_rooms(db, room_specs):
    now = datetime.utcnow()
    rooms = []
    for spec in room_specs:
        doc = room_document(spec)
        db.rooms.update_one(
            {"room_code": doc["room_code"]},
            {"$set": {**doc, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        rooms.append(db.rooms.find_one({"room_code": doc["room_code"]}))
    return rooms


def get_rooms_by_codes(db, room_codes):
    normalized = [room_code(code) for code in room_codes]
    return list(db.rooms.find({"room_code": {"$in": normalized}, "is_active": True}).sort("room_name", 1))
