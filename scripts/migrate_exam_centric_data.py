import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.db_setup import initialize_exam_centric_collections  # noqa: E402
from utils.validation import clean_text  # noqa: E402


def build_migrated_student(old_doc):
    roll_number = clean_text(old_doc.get("roll_number")) or clean_text(old_doc.get("rollnum"))
    if not roll_number:
        return None

    migrated = {
        "roll_number": roll_number,
        "name": clean_text(old_doc.get("name")),
        "department": clean_text(old_doc.get("department")),
        "programme": clean_text(old_doc.get("programme")),
        "programme_type": clean_text(old_doc.get("programme_type")),
        "nta_level": old_doc.get("nta_level"),
        "class_group": clean_text(old_doc.get("class_group")) or clean_text(old_doc.get("sheet_name")),
        "academic_year": clean_text(old_doc.get("academic_year")),
        "status": clean_text(old_doc.get("status")) or "active",
        "legacy_sheet_name": clean_text(old_doc.get("sheet_name")),
        "legacy_year": clean_text(old_doc.get("Year")),
        "legacy_student_id": old_doc.get("_id"),
        "migration_status": "needs_review",
        "migration_notes": [
            "Department, programme type, NTA level, or academic year may need manual confirmation."
        ],
        "updated_at": datetime.utcnow(),
    }
    if "seatnum" in old_doc:
        migrated["archived_legacy_seatnum"] = old_doc["seatnum"]
    return migrated


def migrate(db, dry_run=True):
    initialize_exam_centric_collections(db)
    report = {"read": 0, "inserted": 0, "updated": 0, "skipped": 0, "errors": []}
    for old_doc in db.student.find({}):
        report["read"] += 1
        migrated = build_migrated_student(old_doc)
        if not migrated:
            report["skipped"] += 1
            report["errors"].append({"legacy_id": str(old_doc.get("_id")), "message": "Missing roll number"})
            continue
        if dry_run:
            continue
        try:
            result = db.students.update_one(
                {"roll_number": migrated["roll_number"]},
                {"$set": migrated, "$setOnInsert": {"created_at": datetime.utcnow()}},
                upsert=True,
            )
            if result.upserted_id:
                report["inserted"] += 1
            else:
                report["updated"] += 1
        except DuplicateKeyError as exc:
            report["skipped"] += 1
            report["errors"].append({"roll_number": migrated["roll_number"], "message": str(exc)})
    return report


def main():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        password = os.getenv("MONGO_PASSWORD")
        mongo_uri = "mongodb+srv://stevenkashaigili340:{}@cluster0.fsedap8.mongodb.net/?appName=Cluster0".format(password)
    db_name = os.getenv("MONGO_DB_NAME", "Studetails")
    dry_run = "--apply" not in sys.argv
    client = MongoClient(mongo_uri)
    report = migrate(client[db_name], dry_run=dry_run)
    mode = "DRY RUN" if dry_run else "APPLIED"
    print("{} migration report: {}".format(mode, report))
    if dry_run:
        print("No data was changed. Re-run with --apply after exporting a MongoDB backup.")


if __name__ == "__main__":
    main()
