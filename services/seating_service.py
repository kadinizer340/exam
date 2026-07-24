from collections import defaultdict, deque
from datetime import datetime

try:
    from bson import ObjectId
except ImportError:
    def ObjectId(value):
        return value

from utils.time_utils import time_ranges_overlap


def build_batch_code(session):
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return "SEAT-{}-{}-{}".format(
        str(session["date"]).replace("-", ""),
        str(session["session_name"]).upper(),
        stamp,
    )


def session_time_range(exams, session):
    starts = [exam["start_time"] for exam in exams] or [session["default_start_time"]]
    ends = [exam["end_time"] for exam in exams] or [session["default_start_time"]]
    return min(starts), max(ends)


def room_seats(room):
    half = (int(room["columns"]) + 1) // 2
    side_counts = defaultdict(int)
    for row in range(1, int(room["rows"]) + 1):
        for column in range(1, int(room["columns"]) + 1):
            side = "A" if column <= half else "B"
            side_counts[side] += 1
            yield {
                "seat_number": "{}-{:02d}".format(side, side_counts[side]),
                "seat_row": row,
                "seat_column": column,
                "seat_side": side,
            }


def interleave_candidate_groups(groups):
    queues = [
        deque(group["candidates"])
        for group in sorted(groups, key=lambda item: (-len(item["candidates"]), item["exam"]["exam_code"]))
        if group["candidates"]
    ]
    ordered = []
    while queues:
        next_round = []
        for queue in queues:
            if queue:
                ordered.append(queue.popleft())
            if queue:
                next_round.append(queue)
        queues = next_round
    return ordered


def _load_candidate_groups(db, exams):
    groups = []
    for exam in sorted(exams, key=lambda item: item["exam_code"]):
        candidate_rows = list(db.exam_candidates.find({"exam_id": exam["_id"], "status": "eligible"}).sort("roll_number", 1))
        candidates = []
        for row in candidate_rows:
            student = db.students.find_one({"_id": row["student_id"]})
            if student:
                candidates.append({"candidate": row, "student": student, "exam": exam})
        groups.append({"exam": exam, "candidates": candidates})
    return groups


def _room_conflicts(db, session, rooms, start_time, end_time):
    warnings = []
    for room in rooms:
        existing = db.seat_allocations.find(
            {
                "room_id": room["_id"],
                "date": session["date"],
                "is_active": True,
                "exam_session_id": {"$ne": session["_id"]},
            }
        )
        for allocation in existing:
            if time_ranges_overlap(allocation["start_time"], allocation["end_time"], start_time, end_time):
                warnings.append(
                    "Room {} already has an overlapping allocation from {} to {}.".format(
                        room["room_name"], allocation["start_time"], allocation["end_time"]
                    )
                )
                break
    return warnings


def _unavailable_rooms(db, session, rooms):
    unavailable = []
    for room in rooms:
        availability = db.room_availability.find_one({"room_id": room["_id"], "session_id": session["_id"]})
        if availability and not availability.get("is_available", True):
            unavailable.append("{} is unavailable: {}".format(room["room_name"], availability.get("reason") or "No reason"))
    return unavailable


def preview_session_capacity(db, exam_session_id, room_ids):
    session = db.exam_sessions.find_one({"_id": ObjectId(exam_session_id)})
    if not session:
        raise ValueError("Exam session not found")
    exams = list(db.exams.find({"session_id": session["_id"], "status": "scheduled"}))
    groups = _load_candidate_groups(db, exams)
    total_candidates = sum(len(group["candidates"]) for group in groups)
    rooms = list(db.rooms.find({"_id": {"$in": [ObjectId(room_id) for room_id in room_ids]}, "is_active": True}))
    total_capacity = sum(int(room["capacity"]) for room in rooms)
    start_time, end_time = session_time_range(exams, session)
    warnings = _room_conflicts(db, session, rooms, start_time, end_time)
    warnings.extend(_unavailable_rooms(db, session, rooms))
    if total_capacity < total_candidates:
        warnings.append("{} extra seats are required.".format(total_candidates - total_capacity))
    return {
        "session": session,
        "exam_count": len(exams),
        "total_candidates": total_candidates,
        "total_capacity": total_capacity,
        "rooms": rooms,
        "warnings": warnings,
    }


def generate_seating_for_session(db, exam_session_id, room_ids, generated_by, replace=False):
    session = db.exam_sessions.find_one({"_id": ObjectId(exam_session_id)})
    if not session:
        raise ValueError("Exam session not found")

    exams = list(db.exams.find({"session_id": session["_id"], "status": "scheduled"}).sort("exam_code", 1))
    if not exams:
        raise ValueError("No scheduled exams found for this session")

    rooms = list(db.rooms.find({"_id": {"$in": [ObjectId(room_id) for room_id in room_ids]}, "is_active": True}).sort("room_name", 1))
    if not rooms:
        raise ValueError("Select at least one active room")

    existing_allocations = db.seat_allocations.count_documents({"exam_session_id": session["_id"], "is_active": True})
    if existing_allocations and not replace:
        raise ValueError("This session already has seating. Use replace=1 to regenerate safely.")

    candidate_groups = _load_candidate_groups(db, exams)
    ordered_candidates = interleave_candidate_groups(candidate_groups)
    total_candidates = len(ordered_candidates)
    total_capacity = sum(int(room["capacity"]) for room in rooms)
    start_time, end_time = session_time_range(exams, session)
    warnings = []
    warnings.extend(_room_conflicts(db, session, rooms, start_time, end_time))
    warnings.extend(_unavailable_rooms(db, session, rooms))
    if total_capacity < total_candidates:
        warnings.append("{} extra seats are required.".format(total_candidates - total_capacity))

    now = datetime.utcnow()
    batch_code = build_batch_code(session)
    batch_doc = {
        "batch_code": batch_code,
        "exam_session_id": session["_id"],
        "status": "failed" if warnings else "running",
        "total_candidates": total_candidates,
        "allocated_candidates": 0,
        "unallocated_candidates": total_candidates,
        "rooms_used": len(rooms),
        "generated_by": generated_by,
        "generated_at": now,
        "warnings": warnings,
    }
    batch_id = db.generation_batches.insert_one(batch_doc).inserted_id

    if warnings:
        return {
            "status": "failed",
            "batch_code": batch_code,
            "total_candidates": total_candidates,
            "allocated_candidates": 0,
            "unallocated_candidates": total_candidates,
            "warnings": warnings,
        }

    room_slots = []
    for room in rooms:
        for seat in room_seats(room):
            room_slots.append((room, seat))

    allocations = []
    for index, candidate_info in enumerate(ordered_candidates):
        room, seat = room_slots[index]
        exam = candidate_info["exam"]
        candidate = candidate_info["candidate"]
        allocations.append(
            {
                "exam_session_id": session["_id"],
                "exam_id": exam["_id"],
                "student_id": candidate["student_id"],
                "room_id": room["_id"],
                "seat_number": seat["seat_number"],
                "seat_row": seat["seat_row"],
                "seat_column": seat["seat_column"],
                "seat_side": seat["seat_side"],
                "date": session["date"],
                "session_name": session["session_name"],
                "start_time": exam["start_time"],
                "end_time": exam["end_time"],
                "generated_batch_id": batch_id,
                "generated_batch_code": batch_code,
                "is_active": False,
                "created_at": now,
            }
        )

    if allocations:
        db.seat_allocations.insert_many(allocations, ordered=False)

    db.seat_allocations.update_many(
        {"exam_session_id": session["_id"], "is_active": True},
        {"$set": {"is_active": False, "archived_at": now}},
    )
    db.seat_allocations.update_many(
        {"generated_batch_id": batch_id},
        {"$set": {"is_active": True, "activated_at": now}},
    )
    db.generation_batches.update_one(
        {"_id": batch_id},
        {
            "$set": {
                "status": "completed",
                "allocated_candidates": len(allocations),
                "unallocated_candidates": total_candidates - len(allocations),
            }
        },
    )

    return {
        "status": "completed",
        "batch_code": batch_code,
        "total_candidates": total_candidates,
        "allocated_candidates": len(allocations),
        "unallocated_candidates": total_candidates - len(allocations),
        "warnings": [],
    }


def list_generated_sessions(db):
    session_ids = db.seat_allocations.distinct("exam_session_id", {"is_active": True})
    sessions = list(db.exam_sessions.find({"_id": {"$in": session_ids}}).sort([("date", 1), ("default_start_time", 1)]))
    return [
        {
            "id": str(session["_id"]),
            "label": "{} | {} | {}".format(session["date"], session["session_name"], session["programme_type"]),
            "date": session["date"],
            "session_name": session["session_name"],
            "programme_type": session["programme_type"],
        }
        for session in sessions
    ]


def room_wise_allocations(db, exam_session_id):
    session = db.exam_sessions.find_one({"_id": ObjectId(exam_session_id)})
    if not session:
        raise ValueError("Exam session not found")
    allocations = list(
        db.seat_allocations.find({"exam_session_id": session["_id"], "is_active": True}).sort(
            [("room_id", 1), ("seat_row", 1), ("seat_column", 1)]
        )
    )
    rooms = {}
    for allocation in allocations:
        room = db.rooms.find_one({"_id": allocation["room_id"]}) or {"room_name": "Unknown room"}
        exam = db.exams.find_one({"_id": allocation["exam_id"]}) or {}
        student = db.students.find_one({"_id": allocation["student_id"]}) or {}
        key = str(allocation["room_id"])
        rooms.setdefault(
            key,
            {
                "class_name": room["room_name"],
                "room_name": room["room_name"],
                "session": "{} | {}".format(session["date"], session["session_name"]),
                "seats": [],
                "a": [],
                "b": [],
            },
        )
        seat_payload = {
            "seat_number": allocation["seat_number"],
            "roll_number": student.get("roll_number"),
            "student_name": student.get("name"),
            "exam_code": exam.get("exam_code"),
            "subject": exam.get("subject_name"),
            "nta_level": exam.get("nta_level"),
            "side": allocation["seat_side"],
        }
        rooms[key]["seats"].append(seat_payload)
        if allocation["seat_side"] == "A":
            rooms[key]["a"].append(student.get("roll_number"))
        else:
            rooms[key]["b"].append(student.get("roll_number"))
    return list(rooms.values())
