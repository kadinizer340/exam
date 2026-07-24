from datetime import datetime

try:
    from pymongo.errors import DuplicateKeyError
except ImportError:
    class DuplicateKeyError(Exception):
        pass

from utils.time_utils import (
    calculate_end_time,
    default_start_time_for_session,
    minutes_to_time,
    normalize_date,
    normalize_session_name,
    session_code,
    time_to_minutes,
)
from utils.validation import clean_text, normalize_programme_type, parse_nta_level


SESSION_PROGRAMME_WARNINGS = {
    "Morning": {"Bachelor"},
    "Afternoon": {"Diploma"},
    "Night": {"Bachelor", "Bachelor Night"},
}


def optional_int(value):
    text = clean_text(value)
    return int(float(text)) if text is not None else None


def get_duration_minutes(db, nta_level):
    level = parse_nta_level(nta_level)
    rule = db.exam_duration_rules.find_one({"nta_level": level, "is_active": True})
    if not rule:
        raise ValueError("No active duration rule found for NTA level {}".format(level))
    return int(rule["duration_minutes"])


def session_warnings(session_name, programme_type):
    session = normalize_session_name(session_name)
    programme = normalize_programme_type(programme_type)
    expected = SESSION_PROGRAMME_WARNINGS.get(session, set())
    if expected and programme not in expected:
        return [
            "{} session is usually used for {} examinations.".format(
                session, " or ".join(sorted(expected))
            )
        ]
    return []


def create_or_get_session(
    db,
    date_value,
    session_name,
    programme_type,
    academic_year=None,
    semester=None,
    default_start_time=None,
):
    now = datetime.utcnow()
    normalized_date = normalize_date(date_value)
    normalized_session = normalize_session_name(session_name)
    normalized_programme = normalize_programme_type(programme_type)
    start_time = minutes_to_time(time_to_minutes(default_start_time or default_start_time_for_session(normalized_session)))
    code = session_code(normalized_date, normalized_session, normalized_programme)
    warnings = session_warnings(normalized_session, normalized_programme)

    db.exam_sessions.update_one(
        {"session_code": code},
        {
            "$set": {
                "date": normalized_date,
                "session_name": normalized_session,
                "programme_type": normalized_programme,
                "default_start_time": start_time,
                "academic_year": clean_text(academic_year),
                "semester": optional_int(semester),
                "warnings": warnings,
                "updated_at": now,
            },
            "$setOnInsert": {"status": "draft", "created_at": now},
        },
        upsert=True,
    )
    return db.exam_sessions.find_one({"session_code": code})


def upsert_exam(
    db,
    exam_code,
    subject_name,
    nta_level,
    programme_type,
    session,
    start_time,
    duration_minutes=None,
    departments=None,
    class_groups=None,
    academic_year=None,
    semester=None,
):
    now = datetime.utcnow()
    code = clean_text(exam_code)
    if not code:
        raise ValueError("exam_code is required")
    subject = clean_text(subject_name)
    if not subject:
        raise ValueError("subject_name is required")
    level = parse_nta_level(nta_level)
    programme = normalize_programme_type(programme_type)
    duration = int(float(duration_minutes or get_duration_minutes(db, level)))
    normalized_start_time = minutes_to_time(time_to_minutes(start_time))
    end_time = calculate_end_time(normalized_start_time, duration)
    departments = sorted(set(departments or []))
    class_groups = sorted(set(class_groups or []))

    update = {
        "$set": {
            "exam_code": code,
            "subject_name": subject,
            "nta_level": level,
            "programme_type": programme,
            "session_id": session["_id"],
            "date": session["date"],
            "start_time": normalized_start_time,
            "duration_minutes": duration,
            "end_time": end_time,
            "status": "scheduled",
            "academic_year": clean_text(academic_year) or session.get("academic_year"),
            "semester": optional_int(semester) if clean_text(semester) else session.get("semester"),
            "updated_at": now,
        },
        "$setOnInsert": {"created_at": now},
    }
    if departments:
        update["$addToSet"] = {"departments": {"$each": departments}}
    if class_groups:
        update.setdefault("$addToSet", {})["class_groups"] = {"$each": class_groups}

    db.exams.update_one({"exam_code": code, "session_id": session["_id"]}, update, upsert=True)
    return db.exams.find_one({"exam_code": code, "session_id": session["_id"]})


def build_candidate_filter(exam, department_or_group_values):
    groups = [clean_text(value) for value in department_or_group_values if clean_text(value)]
    base_filter = {
        "status": "active",
        "programme_type": exam["programme_type"],
        "nta_level": exam["nta_level"],
    }
    if not groups or any(group.upper() == "ALL" for group in groups):
        return base_filter

    base_filter["$or"] = [
        {"department": {"$in": groups}},
        {"class_group": {"$in": groups}},
        {"legacy_sheet_name": {"$in": groups}},
    ]
    return base_filter


def register_candidates_for_exam(db, exam, department_or_group_values, registration_source="import"):
    now = datetime.utcnow()
    students = list(db.students.find(build_candidate_filter(exam, department_or_group_values)))
    created = 0
    duplicates = 0
    for student in students:
        try:
            db.exam_candidates.insert_one(
                {
                    "exam_id": exam["_id"],
                    "student_id": student["_id"],
                    "roll_number": student["roll_number"],
                    "registration_source": registration_source,
                    "status": "eligible",
                    "created_at": now,
                }
            )
            created += 1
        except DuplicateKeyError:
            duplicates += 1

    return {
        "matched_students": len(students),
        "created": created,
        "duplicates": duplicates,
    }


def list_session_summaries(db):
    sessions = list(db.exam_sessions.find({}).sort([("date", 1), ("default_start_time", 1)]))
    summaries = []
    for session in sessions:
        exams = list(db.exams.find({"session_id": session["_id"]}).sort("exam_code", 1))
        exam_ids = [exam["_id"] for exam in exams]
        candidate_count = db.exam_candidates.count_documents(
            {"exam_id": {"$in": exam_ids}, "status": "eligible"}
        ) if exam_ids else 0
        allocation_count = db.seat_allocations.count_documents(
            {"exam_session_id": session["_id"], "is_active": True}
        )
        summaries.append(
            {
                **session,
                "exam_count": len(exams),
                "candidate_count": candidate_count,
                "allocation_count": allocation_count,
            }
        )
    return summaries
