from datetime import datetime
import math


MIN_CLASSROOM_CAPACITY = 100
DEFAULT_COLUMNS = 10


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


def clean_room_text(value):
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def validate_room_dimensions(rows, columns):
    rows = int(rows)
    columns = int(columns)
    if rows <= 0 or columns <= 0:
        raise ValueError("Room rows and columns must be positive")
    return rows, columns


def validate_capacity(capacity):
    try:
        parsed = int(float(capacity))
    except (TypeError, ValueError) as exc:
        raise ValueError("Classroom capacity is required") from exc
    if parsed < MIN_CLASSROOM_CAPACITY:
        raise ValueError("Classroom capacity must be at least {} seats.".format(MIN_CLASSROOM_CAPACITY))
    return parsed


def normalize_status(value):
    if value is None:
        return True
    text = str(value).strip().lower()
    if text in {"active", "true", "1", "yes", "on"}:
        return True
    if text in {"inactive", "false", "0", "no", "off"}:
        return False
    raise ValueError("Classroom status must be Active or Inactive")


def layout_from_capacity(capacity, rows=None, columns=None):
    capacity = validate_capacity(capacity)
    if rows and columns:
        return validate_room_dimensions(rows, columns)
    columns = int(columns or DEFAULT_COLUMNS)
    if columns <= 0:
        raise ValueError("Classroom columns must be positive")
    rows = int(math.ceil(capacity / columns))
    return rows, columns


def room_document(spec, enforce_min_capacity=True):
    room_name = clean_room_text(spec.get("room_name") or spec.get("classroom_name"))
    if not room_name:
        raise ValueError("Classroom name is required")

    code = clean_room_text(spec.get("room_code") or spec.get("classroom_code")) or room_code(room_name)
    legacy_capacity = None
    if spec.get("rows") and spec.get("columns"):
        rows, columns = validate_room_dimensions(spec["rows"], spec["columns"])
        legacy_capacity = rows * columns
    else:
        rows = None
        columns = spec.get("columns") or DEFAULT_COLUMNS

    raw_capacity = spec.get("capacity")
    if raw_capacity in (None, ""):
        raw_capacity = max(legacy_capacity or 0, MIN_CLASSROOM_CAPACITY) if enforce_min_capacity else legacy_capacity

    capacity = validate_capacity(raw_capacity) if enforce_min_capacity else int(raw_capacity)
    if rows is None:
        rows, columns = layout_from_capacity(capacity, columns=columns)

    return {
        "room_code": room_code(code),
        "room_name": room_name,
        "building": clean_room_text(spec.get("building")),
        "floor": clean_room_text(spec.get("floor")),
        "rows": rows,
        "columns": columns,
        "capacity": capacity,
        "legacy_layout_capacity": legacy_capacity,
        "is_active": normalize_status(spec.get("status", spec.get("is_active", True))),
        "is_deleted": bool(spec.get("is_deleted", False)),
        "notes": clean_room_text(spec.get("notes")),
    }


def seed_default_rooms(db):
    return ensure_rooms(db, DEFAULT_ROOMS, update_existing=False)


def migrate_existing_room_records(db):
    now = datetime.utcnow()
    updated = 0
    for room in db.rooms.find({"is_deleted": {"$ne": True}}):
        capacity = room.get("capacity")
        legacy_capacity = room.get("legacy_layout_capacity")
        if legacy_capacity is None and room.get("rows") and room.get("columns"):
            legacy_capacity = int(room["rows"]) * int(room["columns"])
        set_values = {}
        if legacy_capacity is not None and room.get("legacy_layout_capacity") is None:
            set_values["legacy_layout_capacity"] = legacy_capacity
        if capacity is None or int(capacity) < MIN_CLASSROOM_CAPACITY:
            set_values["capacity"] = MIN_CLASSROOM_CAPACITY
        if "is_deleted" not in room:
            set_values["is_deleted"] = False
        if set_values:
            set_values["updated_at"] = now
            db.rooms.update_one({"_id": room["_id"]}, {"$set": set_values})
            updated += 1
    return updated


def ensure_rooms(db, room_specs, update_existing=False):
    now = datetime.utcnow()
    rooms = []
    for spec in room_specs:
        doc = room_document(spec)
        if update_existing:
            db.rooms.update_one(
                {"room_code": doc["room_code"]},
                {"$set": {**doc, "updated_at": now}, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
        else:
            db.rooms.update_one(
                {"room_code": doc["room_code"]},
                {"$setOnInsert": {**doc, "created_at": now, "updated_at": now}},
                upsert=True,
            )
        rooms.append(db.rooms.find_one({"room_code": doc["room_code"]}))
    return rooms


def get_rooms_by_codes(db, room_codes):
    normalized = [room_code(code) for code in room_codes]
    return list(
        db.rooms.find(
            {
                "room_code": {"$in": normalized},
                "is_active": True,
                "is_deleted": {"$ne": True},
            }
        ).sort("room_name", 1)
    )


def list_rooms(db, query=None, status=None, building=None, sort="room_name", page=1, per_page=20):
    filters = {"is_deleted": {"$ne": True}}
    if query:
        filters["$or"] = [
            {"room_code": {"$regex": query, "$options": "i"}},
            {"room_name": {"$regex": query, "$options": "i"}},
            {"building": {"$regex": query, "$options": "i"}},
        ]
    if status == "active":
        filters["is_active"] = True
    elif status == "inactive":
        filters["is_active"] = False
    if building:
        filters["building"] = building

    sort_map = {
        "code": "room_code",
        "name": "room_name",
        "building": "building",
        "capacity": "capacity",
        "updated": "updated_at",
    }
    sort_field = sort_map.get(sort, "room_name")
    direction = -1 if sort == "updated" else 1
    page = max(int(page or 1), 1)
    per_page = max(min(int(per_page or 20), 100), 1)
    skip = (page - 1) * per_page
    cursor = db.rooms.find(filters).sort(sort_field, direction).skip(skip).limit(per_page)
    total = db.rooms.count_documents(filters)
    return list(cursor), total


def room_form_payload(payload):
    return {
        "room_code": payload.get("room_code") or payload.get("classroom_code"),
        "room_name": payload.get("room_name") or payload.get("classroom_name"),
        "building": payload.get("building"),
        "floor": payload.get("floor"),
        "capacity": payload.get("capacity"),
        "status": payload.get("status", "active"),
        "notes": payload.get("notes"),
    }


def create_room(db, payload):
    now = datetime.utcnow()
    doc = room_document(room_form_payload(payload))
    existing = db.rooms.find_one({"room_code": doc["room_code"], "is_deleted": {"$ne": True}})
    if existing:
        raise ValueError("Classroom code already exists.")
    doc["created_at"] = now
    doc["updated_at"] = now
    result = db.rooms.insert_one(doc)
    return db.rooms.find_one({"_id": result.inserted_id})


def update_room(db, room_id, payload):
    from bson import ObjectId

    now = datetime.utcnow()
    existing = db.rooms.find_one({"_id": ObjectId(room_id), "is_deleted": {"$ne": True}})
    if not existing:
        raise ValueError("Classroom not found.")
    form_data = room_form_payload(payload)
    form_data["room_code"] = existing["room_code"]
    form_data["rows"] = existing.get("rows")
    form_data["columns"] = existing.get("columns")
    doc = room_document(form_data)
    db.rooms.update_one(
        {"_id": existing["_id"]},
        {
            "$set": {
                "room_name": doc["room_name"],
                "building": doc.get("building"),
                "floor": doc.get("floor"),
                "capacity": doc["capacity"],
                "rows": doc["rows"],
                "columns": doc["columns"],
                "is_active": doc["is_active"],
                "notes": doc.get("notes"),
                "updated_at": now,
            }
        },
    )
    return db.rooms.find_one({"_id": existing["_id"]})


def toggle_room_status(db, room_id):
    from bson import ObjectId

    now = datetime.utcnow()
    room = db.rooms.find_one({"_id": ObjectId(room_id), "is_deleted": {"$ne": True}})
    if not room:
        raise ValueError("Classroom not found.")
    db.rooms.update_one(
        {"_id": room["_id"]},
        {"$set": {"is_active": not room.get("is_active", True), "updated_at": now}},
    )
    return db.rooms.find_one({"_id": room["_id"]})


def archive_room(db, room_id):
    from bson import ObjectId

    now = datetime.utcnow()
    room = db.rooms.find_one({"_id": ObjectId(room_id), "is_deleted": {"$ne": True}})
    if not room:
        raise ValueError("Classroom not found.")
    if db.seat_allocations.count_documents({"room_id": room["_id"]}) == 0:
        db.rooms.delete_one({"_id": room["_id"]})
        return "deleted"
    db.rooms.update_one(
        {"_id": room["_id"]},
        {
            "$set": {
                "is_deleted": True,
                "is_active": False,
                "deleted_at": now,
                "updated_at": now,
            }
        },
    )
    return "archived"
