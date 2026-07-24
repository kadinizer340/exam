from datetime import datetime
import math
from numbers import Integral, Real

try:
    import pandas as pd
except ImportError:
    class _PandasFallback:
        @staticmethod
        def isna(value):
            return value is None or (isinstance(value, float) and math.isnan(value))

        @staticmethod
        def read_excel(*args, **kwargs):
            raise ImportError("Pandas is required to import Excel workbooks.")

    pd = _PandasFallback()
try:
    from pymongo.errors import DuplicateKeyError
except ImportError:
    class DuplicateKeyError(Exception):
        pass

from services.exam_service import (
    create_or_get_session,
    register_candidates_for_exam,
    upsert_exam,
)
from utils.time_utils import default_start_time_for_session, normalize_date, normalize_session_name
from utils.validation import (
    clean_text,
    normalize_column_name,
    normalize_programme_type,
    parse_nta_level,
    split_multi_value,
)


STUDENT_ALIASES = {
    "rollnum": "roll_number",
    "roll_no": "roll_number",
    "roll": "roll_number",
    "student_name": "name",
    "program": "programme",
    "level": "nta_level",
    "class": "class_group",
    "group": "class_group",
}

TIMETABLE_ALIASES = {
    "subject": "subject_name",
    "course": "subject_name",
    "course_code": "exam_code",
    "program": "programme_type",
    "programme": "programme_type",
    "session_name": "session",
    "level": "nta_level",
    "department": "department_or_group",
    "class_group": "department_or_group",
    "group": "department_or_group",
}

STUDENT_REQUIRED_COLUMNS = [
    "roll_number",
    "name",
    "department",
    "programme",
    "programme_type",
    "nta_level",
    "class_group",
    "academic_year",
]

TIMETABLE_REQUIRED_COLUMNS = [
    "exam_code",
    "subject_name",
    "date",
    "programme_type",
    "nta_level",
    "session",
    "start_time",
    "department_or_group",
]


def allowed_excel_file(filename):
    return bool(filename) and filename.lower().endswith((".xls", ".xlsx"))


def _normalize_dataframe_columns(frame, aliases):
    renamed = {}
    for column in frame.columns:
        normalized = normalize_column_name(column)
        renamed[column] = aliases.get(normalized, normalized)
    return frame.rename(columns=renamed)


def _read_workbook_rows(path, aliases):
    sheets = pd.read_excel(path, sheet_name=None)
    rows = []
    for sheet_name, frame in sheets.items():
        frame = _normalize_dataframe_columns(frame, aliases)
        for index, raw_row in frame.iterrows():
            if raw_row.dropna().empty:
                continue
            row = raw_row.to_dict()
            row["_sheet_name"] = sheet_name
            row["_row_number"] = int(index) + 2
            rows.append(row)
    return rows


def _missing_columns(row, required):
    return [column for column in required if column not in row or clean_text(row.get(column)) is None]


def normalize_optional_int(value, field_name):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = float(text)
        except ValueError as exc:
            raise ValueError("{} must be a whole number".format(field_name)) from exc
    elif isinstance(value, Integral):
        parsed = int(value)
    elif isinstance(value, Real):
        parsed = float(value)
    else:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("{} must be a whole number".format(field_name)) from exc

    if parsed != int(parsed):
        raise ValueError("{} must be a whole number".format(field_name))
    return int(parsed)


def import_students_from_excel(db, path, default_metadata=None, strict=False):
    default_metadata = default_metadata or {}
    summary = {
        "total_rows": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "errors": [],
        "warnings": [],
        "preview": {},
    }
    rows = _read_workbook_rows(path, STUDENT_ALIASES)
    summary["total_rows"] = len(rows)
    seen_roll_numbers = set()
    now = datetime.utcnow()

    for row in rows:
        sheet_name = row["_sheet_name"]
        summary["preview"].setdefault(sheet_name, 0)
        summary["preview"][sheet_name] += 1
        missing = _missing_columns(row, ["roll_number", "name"])
        if missing:
            summary["errors"].append(
                {"row": row["_row_number"], "sheet": sheet_name, "message": "Missing {}".format(", ".join(missing))}
            )
            summary["skipped"] += 1
            continue

        strict_missing = _missing_columns(row, STUDENT_REQUIRED_COLUMNS)
        migration_status = "ready"
        if strict_missing:
            if strict:
                summary["errors"].append(
                    {
                        "row": row["_row_number"],
                        "sheet": sheet_name,
                        "message": "Missing {}".format(", ".join(strict_missing)),
                    }
                )
                summary["skipped"] += 1
                continue
            migration_status = "needs_review"
            summary["warnings"].append(
                "Row {} in {} is missing {}; stored for manual review.".format(
                    row["_row_number"], sheet_name, ", ".join(strict_missing)
                )
            )

        roll_number = clean_text(row.get("roll_number"))
        if roll_number in seen_roll_numbers:
            summary["errors"].append(
                {"row": row["_row_number"], "sheet": sheet_name, "message": "Duplicate roll number in import"}
            )
            summary["skipped"] += 1
            continue
        seen_roll_numbers.add(roll_number)

        try:
            nta_level = parse_nta_level(row.get("nta_level")) if clean_text(row.get("nta_level")) else None
        except ValueError as exc:
            summary["errors"].append({"row": row["_row_number"], "sheet": sheet_name, "message": str(exc)})
            summary["skipped"] += 1
            continue

        try:
            programme_type = normalize_programme_type(row.get("programme_type")) if clean_text(row.get("programme_type")) else None
        except ValueError as exc:
            summary["errors"].append({"row": row["_row_number"], "sheet": sheet_name, "message": str(exc)})
            summary["skipped"] += 1
            continue

        doc = {
            "roll_number": roll_number,
            "name": clean_text(row.get("name")),
            "department": clean_text(row.get("department")),
            "programme": clean_text(row.get("programme")),
            "programme_type": programme_type,
            "nta_level": nta_level,
            "class_group": clean_text(row.get("class_group")),
            "academic_year": clean_text(row.get("academic_year")),
            "status": clean_text(row.get("status")) or "active",
            "legacy_sheet_name": sheet_name,
            "legacy_year": default_metadata.get("legacy_year"),
            "migration_status": migration_status,
            "updated_at": now,
        }
        if clean_text(row.get("rollnum")):
            doc["legacy_rollnum"] = row.get("rollnum")

        try:
            result = db.students.update_one(
                {"roll_number": roll_number},
                {"$set": doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
        except DuplicateKeyError:
            summary["errors"].append(
                {"row": row["_row_number"], "sheet": sheet_name, "message": "Roll number already exists"}
            )
            summary["skipped"] += 1
            continue

        if result.upserted_id:
            summary["inserted"] += 1
        else:
            summary["updated"] += 1

    return summary


def import_timetable_from_excel(db, path, default_metadata=None, strict=True):
    default_metadata = default_metadata or {}
    summary = {
        "total_rows": 0,
        "sessions_created_or_reused": 0,
        "exams_created_or_updated": 0,
        "candidates_registered": 0,
        "duplicate_candidates": 0,
        "warnings": [],
        "errors": [],
    }
    rows = _read_workbook_rows(path, TIMETABLE_ALIASES)
    summary["total_rows"] = len(rows)
    session_codes = set()
    exam_keys = set()

    for row in rows:
        missing = _missing_columns(row, TIMETABLE_REQUIRED_COLUMNS)
        if missing:
            message = "Missing {}".format(", ".join(missing))
            if strict:
                summary["errors"].append(
                    {"row": row["_row_number"], "sheet": row["_sheet_name"], "message": message}
                )
                continue
            summary["warnings"].append("{} in row {}".format(message, row["_row_number"]))

        try:
            session_name = normalize_session_name(row.get("session"))
            programme_type = normalize_programme_type(row.get("programme_type"))
            nta_level = parse_nta_level(row.get("nta_level"))
            date_value = normalize_date(row.get("date"))
            start_time = clean_text(row.get("start_time")) or default_start_time_for_session(session_name)
            session = create_or_get_session(
                db,
                date_value,
                session_name,
                programme_type,
                academic_year=row.get("academic_year") or default_metadata.get("academic_year"),
                semester=row.get("semester") or default_metadata.get("semester"),
                default_start_time=start_time,
            )
            departments_or_groups = split_multi_value(row.get("department_or_group"))
            exam = upsert_exam(
                db,
                exam_code=row.get("exam_code"),
                subject_name=row.get("subject_name"),
                nta_level=nta_level,
                programme_type=programme_type,
                session=session,
                start_time=start_time,
                duration_minutes=normalize_optional_int(row.get("duration_minutes"), "duration_minutes"),
                departments=departments_or_groups,
                class_groups=departments_or_groups,
                academic_year=row.get("academic_year") or default_metadata.get("academic_year"),
                semester=row.get("semester") or default_metadata.get("semester"),
            )
            candidate_result = register_candidates_for_exam(db, exam, departments_or_groups)
        except Exception as exc:
            summary["errors"].append(
                {"row": row["_row_number"], "sheet": row["_sheet_name"], "message": str(exc)}
            )
            continue

        session_codes.add(session["session_code"])
        exam_keys.add("{}:{}".format(exam["exam_code"], session["_id"]))
        summary["candidates_registered"] += candidate_result["created"]
        summary["duplicate_candidates"] += candidate_result["duplicates"]
        if candidate_result["matched_students"] == 0:
            summary["warnings"].append(
                "No students matched exam {} row {}.".format(exam["exam_code"], row["_row_number"])
            )

    summary["sessions_created_or_reused"] = len(session_codes)
    summary["exams_created_or_updated"] = len(exam_keys)
    return summary
