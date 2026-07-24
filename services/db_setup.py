from datetime import datetime

from pymongo import ASCENDING


DEFAULT_DURATION_RULES = [
    {"nta_level": 4, "duration_minutes": 120, "label": "2 hours"},
    {"nta_level": 5, "duration_minutes": 120, "label": "2 hours"},
    {"nta_level": 6, "duration_minutes": 150, "label": "2 hours 30 minutes"},
    {"nta_level": 7, "duration_minutes": 180, "label": "3 hours"},
    {"nta_level": 8, "duration_minutes": 180, "label": "3 hours"},
]


def ensure_indexes(db):
    db.users.create_index([("username", ASCENDING)], unique=True)
    db.students.create_index([("roll_number", ASCENDING)], unique=True)
    db.exam_sessions.create_index([("session_code", ASCENDING)], unique=True)
    db.exam_duration_rules.create_index([("nta_level", ASCENDING)], unique=True)
    db.exams.create_index([("exam_code", ASCENDING), ("session_id", ASCENDING)], unique=True)
    db.exam_candidates.create_index([("exam_id", ASCENDING), ("student_id", ASCENDING)], unique=True)
    db.rooms.create_index([("room_code", ASCENDING)], unique=True)
    db.room_availability.create_index([("room_id", ASCENDING), ("session_id", ASCENDING)], unique=True)
    db.generation_batches.create_index([("batch_code", ASCENDING)], unique=True)
    db.seat_allocations.create_index(
        [("exam_id", ASCENDING), ("student_id", ASCENDING)],
        unique=True,
        partialFilterExpression={"is_active": True},
    )
    db.seat_allocations.create_index(
        [("exam_session_id", ASCENDING), ("room_id", ASCENDING), ("seat_number", ASCENDING)],
        unique=True,
        partialFilterExpression={"is_active": True},
    )


def seed_duration_rules(db):
    now = datetime.utcnow()
    seeded = 0
    for rule in DEFAULT_DURATION_RULES:
        result = db.exam_duration_rules.update_one(
            {"nta_level": rule["nta_level"]},
            {
                "$setOnInsert": {
                    **rule,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        if result.upserted_id:
            seeded += 1
    return seeded


def initialize_exam_centric_collections(db):
    ensure_indexes(db)
    return seed_duration_rules(db)
