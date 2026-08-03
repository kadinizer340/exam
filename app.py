from functools import wraps

from flask import Flask, flash, render_template, request, redirect, url_for, jsonify, session
from markupsafe import Markup
from datetime import datetime
from static.converter import excel_to_json
import os
import json
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson import ObjectId

from services.db_setup import initialize_exam_centric_collections
from services.exam_service import list_session_summaries
from services.import_service import (
    allowed_excel_file,
    import_students_from_excel,
    import_timetable_from_excel,
)
from services.lookup_service import student_allocations_by_roll_number
from services.room_service import (
    archive_room,
    create_room,
    get_rooms_by_codes,
    list_rooms as list_classrooms,
    migrate_existing_room_records,
    room_code,
    seed_default_rooms,
    toggle_room_status,
    update_room,
)
from services.seating_service import (
    generate_seating_for_session,
    list_generated_sessions,
    preview_session_capacity,
    room_wise_allocations,
)

# configuring flask

app = Flask(__name__)
app.debug = os.getenv("FLASK_DEBUG") == "1"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv("MAX_UPLOAD_MB", "16")) * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# app.config['UPLOAD_FOLDER'] = r'C:\Users\hp\Desktop\Exam-Seat-Arrangement\uploads'

# Load environment variables from .env file
load_dotenv()

app.secret_key = os.getenv("SECRET_KEY") or "development-secret-change-me"

# Get the MongoDB connection string from the environment variable
# to set environment variable setx MONGO_PASSWORD your_pass
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_URI = os.getenv(
    "MONGO_URI",
    f"mongodb+srv://stevenkashaigili340:{MONGO_PASSWORD}@cluster0.fsedap8.mongodb.net/?appName=Cluster0",
)

# Connect to MongoDB
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)

# client = pymongo.MongoClient(
#     "mongodb://localhost:27017")

db = client[os.getenv("MONGO_DB_NAME", "Studetails")]
usercollections = db.users
stucollections = db.student
students_collection = db.students

# global variables
listy = []
filled = False
data2 = None
data3 = None
data4 = None
timetable2 = None
timetable3 = None
timetable4 = None
with open('static/dates.txt', 'r') as datefiles:
    dates = json.load(datefiles)

try:
    initialize_exam_centric_collections(db)
    seed_default_rooms(db)
    migrate_existing_room_records(db)
except PyMongoError:
    # Keep the app importable if MongoDB is temporarily unavailable.
    pass


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("username"):
            flash("Please sign in to continue.", "login-error")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper


def save_uploaded_workbook(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_excel_file(file_storage.filename):
        raise ValueError("Only .xls and .xlsx files are supported.")
    filename = secure_filename(file_storage.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file_storage.save(path)
    return path


def selected_room_codes_from_request(items):
    return [room_code(item) for item in items]


def room_to_classroom_card(room):
    columns = int(room.get("columns") or 10)
    rows = int(room.get("rows") or 10)
    return {
        "id": str(room["_id"]),
        "name": room.get("room_name"),
        "code": room.get("room_code"),
        "building": room.get("building") or "Unassigned",
        "columns": columns,
        "rows": rows,
        "capacity": int(room.get("capacity") or columns * rows),
    }


def classroom_query_context():
    page = int(request.args.get("page", 1) or 1)
    per_page = 20
    query = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    building = request.args.get("building", "").strip()
    sort = request.args.get("sort", "name").strip()
    rooms, total = list_classrooms(
        db,
        query=query,
        status=status or None,
        building=building or None,
        sort=sort,
        page=page,
        per_page=per_page,
    )
    buildings = sorted(
        [
            item
            for item in db.rooms.distinct("building", {"is_deleted": {"$ne": True}})
            if item
        ]
    )
    return {
        "classrooms": rooms,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max((total + per_page - 1) // per_page, 1),
        "query": query,
        "status_filter": status,
        "building_filter": building,
        "sort": sort,
        "buildings": buildings,
    }

# routes
# homepage
@app.route('/')
def index():
    return render_template('home.html')

# signup page for admin
@app.route('/admin/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        # Check if the username already exists in the database
        if usercollections.find_one({'username': username}):
            flash('Username already exists', 'registration-error')
            return redirect(url_for('register'))
        
        else:
            # If the username is unique, insert the new user into the database
            usercollections.insert_one(
                {
                    'username': username,
                    'password_hash': generate_password_hash(password),
                    'role': 'admin',
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow(),
                })
            flash('Registration successful!', 'registration-success')
            return redirect(url_for('login'))
    else:
        return render_template('adminlogin.html')


# login page for admin
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Retrieve the username and password from the form
        username = request.form['username'].strip()
        password = request.form['password']
        
        # Check if the username and password match a user in the database
        user = usercollections.find_one({'username': username})
        
        valid_password = False
        if user and user.get("password_hash"):
            valid_password = check_password_hash(user["password_hash"], password)
        elif user and user.get("password") == password:
            valid_password = True
            usercollections.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "password_hash": generate_password_hash(password),
                        "updated_at": datetime.utcnow(),
                    },
                    "$unset": {"password": ""},
                },
            )

        if valid_password:
            # If the user exists, store the username in the session
            session['username'] = username
            return redirect(url_for('admin'))
        else:
            flash('Invalid username or password', 'login-error')
            return redirect(url_for('login'))
    else:
        return render_template('adminlogin.html')


# main page of admin where he can choose the classes
@app.route('/admin')
@login_required
def admin():
    stats = {
        "students": students_collection.count_documents({}),
        "rooms": db.rooms.count_documents({"is_active": True}),
        "sessions": db.exam_sessions.count_documents({}),
        "exams": db.exams.count_documents({}),
        "allocations": db.seat_allocations.count_documents({"is_active": True}),
        "batches": db.generation_batches.count_documents({}),
    }
    return render_template('adminhome.html', stats=stats)


# When student enters their rollnumber
    # their corresponding seating is displayed
@app.route('/student', methods=['GET', 'POST'])
def student():
    if request.method == 'POST':
        roll = request.form['roll_num'].strip()
        student_data, allocations = student_allocations_by_roll_number(db, roll)

        if student_data is None:
            legacy_query = {'rollnum': int(roll)} if roll.isdigit() else {'rollnum': roll}
            legacy_student = stucollections.find_one(legacy_query)
            legacy_seats = legacy_student.get('seatnum') if legacy_student else None
            return render_template('studentpage.html', roll_num=roll, seat_num=legacy_seats, legacy_lookup=True)

        return render_template(
            'studentpage.html',
            roll_num=roll,
            student=student_data,
            seat_num=allocations,
            legacy_lookup=False,
        )
    else:
        return render_template('studentpage.html')


@app.route('/class', methods=['GET'])
@login_required
def classchoose():
    active_rooms = list(
        db.rooms.find({"is_active": True, "is_deleted": {"$ne": True}}).sort(
            [("building", 1), ("room_name", 1)]
        )
    )
    return render_template(
        'classavailable.html',
        classrooms=[room_to_classroom_card(room) for room in active_rooms],
    )


@app.route('/classrooms', methods=['GET', 'POST'])
@login_required
def classroom_management():
    if request.method == 'POST':
        try:
            create_room(db, request.form)
            flash('Classroom saved successfully.', 'success')
            return redirect(url_for('classroom_management'))
        except Exception as exc:
            flash(str(exc), 'danger')
    return render_template('classrooms.html', **classroom_query_context())


@app.route('/classrooms/<room_id>/edit', methods=['POST'])
@login_required
def classroom_edit(room_id):
    try:
        update_room(db, room_id, request.form)
        flash('Classroom updated successfully.', 'success')
    except Exception as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('classroom_management'))


@app.route('/classrooms/<room_id>/toggle', methods=['POST'])
@login_required
def classroom_toggle(room_id):
    try:
        room = toggle_room_status(db, room_id)
        status = "activated" if room.get("is_active") else "deactivated"
        flash('Classroom {}.'.format(status), 'success')
    except Exception as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('classroom_management'))


@app.route('/classrooms/<room_id>/delete', methods=['POST'])
@login_required
def classroom_delete(room_id):
    try:
        result = archive_room(db, room_id)
        flash('Classroom {} successfully.'.format(result), 'success')
    except Exception as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('classroom_management'))


# page for uploading student details
@app.route('/uploaddata', methods=['GET'])
@login_required
def uploadpage():
    return render_template('studentdataupload.html')

# when the data is submitted from /uploaddata or studentdataupload.html the data is processed here
# Here the data is checked and uploaded to the database
    # with sheetname as classname,year,classroom:which is the class they are going to be seated
# the data is also passed to "listy" for later usage in /seating
# finally the uploaded data is displayed in uploadeddata.html


@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    upload_specs = [
        ("file", None),
        ("file2", "SecondYear"),
        ("file3", "ThirdYear"),
        ("file4", "FourthYear"),
    ]
    summaries = []
    previews = {}

    for field_name, legacy_year in upload_specs:
        uploaded_file = request.files.get(field_name)
        if not uploaded_file or not uploaded_file.filename:
            continue
        try:
            path = save_uploaded_workbook(uploaded_file)
            summary = import_students_from_excel(
                db,
                path,
                default_metadata={"legacy_year": legacy_year},
                strict=False,
            )
            summary["filename"] = uploaded_file.filename
            summary["legacy_year"] = legacy_year
            summaries.append(summary)
            previews[field_name] = excel_to_json(path)
        except Exception as exc:
            summaries.append(
                {
                    "filename": uploaded_file.filename,
                    "legacy_year": legacy_year,
                    "total_rows": 0,
                    "inserted": 0,
                    "updated": 0,
                    "skipped": 0,
                    "warnings": [],
                    "errors": [{"message": str(exc)}],
                    "preview": {},
                }
            )

    if not summaries:
        flash('No files uploaded', 'error')
        return render_template('studentdataupload.html')

    global data2, data3, data4
    data2 = previews.get("file") or previews.get("file2")
    data3 = previews.get("file3")
    data4 = previews.get("file4")

    imported = sum(item.get("inserted", 0) + item.get("updated", 0) for item in summaries)
    errors = sum(len(item.get("errors", [])) for item in summaries)
    if errors:
        flash('Student import completed with validation errors. Review the summary below.', 'danger')
    else:
        flash('Student import completed: {} records inserted or updated.'.format(imported), 'success')

    return render_template('uploadeddata.html', summaries=summaries, data2=data2, data3=data3, data4=data4)

# page for displaying the data via "GET" method
@app.route('/displaydata', methods=['GET'])
@login_required
def display_data():
    recent_students = list(
        students_collection.find(
            {},
            {
                "roll_number": 1,
                "name": 1,
                "department": 1,
                "programme_type": 1,
                "nta_level": 1,
                "class_group": 1,
                "migration_status": 1,
            },
        ).sort("updated_at", -1).limit(50)
    )
    return render_template('displaydata.html', data2=data2, data3=data3, data4=data4, students=recent_students)

# here the timetable is uploaded via timetableupload.html
# the filename is checked
@app.route('/timetable', methods=['GET', 'POST'])
@login_required
def timetable():
    if request.method == 'POST':
        upload_specs = ["file", "file2", "file3", "file4"]
        summaries = []
        previews = {}

        for field_name in upload_specs:
            uploaded_file = request.files.get(field_name)
            if not uploaded_file or not uploaded_file.filename:
                continue
            try:
                path = save_uploaded_workbook(uploaded_file)
                summary = import_timetable_from_excel(db, path, strict=True)
                summary["filename"] = uploaded_file.filename
                summaries.append(summary)
                previews[field_name] = excel_to_json(path)
            except Exception as exc:
                summaries.append(
                    {
                        "filename": uploaded_file.filename,
                        "total_rows": 0,
                        "sessions_created_or_reused": 0,
                        "exams_created_or_updated": 0,
                        "candidates_registered": 0,
                        "duplicate_candidates": 0,
                        "warnings": [],
                        "errors": [{"message": str(exc)}],
                    }
                )

        if not summaries:
            flash('No files uploaded', 'error')
            return render_template('timetableupload.html')

        global timetable2, timetable3, timetable4, dates
        timetable2 = previews.get("file") or previews.get("file2")
        timetable3 = previews.get("file3")
        timetable4 = previews.get("file4")
        dates = sorted({session_doc["date"] for session_doc in db.exam_sessions.find({}, {"date": 1})})
        with open('static/dates.txt', 'w') as f:
            json.dump(dates, f, indent=4)

        errors = sum(len(item.get("errors", [])) for item in summaries)
        exams = sum(item.get("exams_created_or_updated", 0) for item in summaries)
        candidates = sum(item.get("candidates_registered", 0) for item in summaries)
        if errors:
            flash('Timetable import completed with validation errors. Review the summary below.', 'danger')
        else:
            flash('Timetable import completed: {} exams prepared and {} candidates registered.'.format(exams, candidates), 'success')
        return render_template('timetableupload.html', summaries=summaries, sessions=list_session_summaries(db))
    return render_template('timetableupload.html', sessions=list_session_summaries(db))

# the timetable is fetched and displayed here
@app.route('/viewtimetable', methods=['GET'])
@login_required
def view_timetable():
    sessions = []
    for session_doc in list_session_summaries(db):
        exams = []
        for exam in db.exams.find({"session_id": session_doc["_id"]}).sort("exam_code", 1):
            exams.append({
                "exam_code": exam.get("exam_code"),
                "subject_name": exam.get("subject_name"),
                "nta_level": exam.get("nta_level"),
                "programme_type": exam.get("programme_type"),
                "start_time": exam.get("start_time"),
                "end_time": exam.get("end_time"),
                "candidate_count": db.exam_candidates.count_documents({"exam_id": exam["_id"], "status": "eligible"}),
            })
        sessions.append({
            "id": str(session_doc["_id"]),
            "session_code": session_doc.get("session_code"),
            "date": session_doc.get("date"),
            "session_name": session_doc.get("session_name"),
            "programme_type": session_doc.get("programme_type"),
            "exam_count": session_doc.get("exam_count"),
            "candidate_count": session_doc.get("candidate_count"),
            "allocation_count": session_doc.get("allocation_count"),
            "exams": exams,
        })
    return jsonify(sessions)


# unlike the /displaydata which displays the uploaded data
# this route fetches the uploaded data from the mongodb
@app.route('/viewdata', methods=['GET'])
@login_required
def view_data():
    documents = students_collection.find(
        {},
        {
            'name': 1,
            'roll_number': 1,
            'department': 1,
            'programme_type': 1,
            'nta_level': 1,
            'class_group': 1,
            'academic_year': 1,
            'migration_status': 1,
        },
    ).sort('roll_number', 1)
    data = []
    for doc in documents:
        data.append({
            'name': doc.get('name'),
            'roll_number': doc.get('roll_number'),
            'department': doc.get('department'),
            'programme_type': doc.get('programme_type'),
            'nta_level': doc.get('nta_level'),
            'class_group': doc.get('class_group'),
            'academic_year': doc.get('academic_year'),
            'migration_status': doc.get('migration_status'),
        })
    return jsonify(data)


@app.route('/sessions', methods=['GET'])
@login_required
def list_sessions():
    return jsonify(
        [
            {
                "id": str(item["_id"]),
                "session_code": item.get("session_code"),
                "date": item.get("date"),
                "session_name": item.get("session_name"),
                "programme_type": item.get("programme_type"),
                "default_start_time": item.get("default_start_time"),
                "exam_count": item.get("exam_count"),
                "candidate_count": item.get("candidate_count"),
                "allocation_count": item.get("allocation_count"),
                "warnings": item.get("warnings", []),
            }
            for item in list_session_summaries(db)
        ]
    )


@app.route('/exams', methods=['GET'])
@login_required
def list_exams():
    exams = []
    for exam in db.exams.find({}).sort([("date", 1), ("start_time", 1), ("exam_code", 1)]):
        session_doc = db.exam_sessions.find_one({"_id": exam.get("session_id")}) or {}
        exams.append(
            {
                "id": str(exam["_id"]),
                "exam_code": exam.get("exam_code"),
                "subject_name": exam.get("subject_name"),
                "nta_level": exam.get("nta_level"),
                "programme_type": exam.get("programme_type"),
                "date": exam.get("date"),
                "session": session_doc.get("session_name"),
                "start_time": exam.get("start_time"),
                "end_time": exam.get("end_time"),
                "candidate_count": db.exam_candidates.count_documents({"exam_id": exam["_id"], "status": "eligible"}),
            }
        )
    return jsonify(exams)


@app.route('/rooms', methods=['GET', 'POST'])
@login_required
def rooms():
    if request.method == 'POST':
        payload = request.get_json(silent=True) or request.form
        try:
            room = create_room(db, payload)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"room_id": str(room["_id"]), "room_code": room["room_code"]})

    return jsonify(
        [
            {
                "id": str(room["_id"]),
                "room_code": room.get("room_code"),
                "room_name": room.get("room_name"),
                "building": room.get("building"),
                "rows": room.get("rows"),
                "columns": room.get("columns"),
                "capacity": room.get("capacity"),
                "is_active": room.get("is_active"),
            }
            for room in db.rooms.find({"is_deleted": {"$ne": True}}).sort("room_name", 1)
        ]
    )


@app.route('/rooms/availability', methods=['POST'])
@login_required
def configure_room_availability():
    payload = request.get_json(silent=True) or request.form
    try:
        room_id = ObjectId(payload.get("room_id"))
        session_id = ObjectId(payload.get("session_id"))
        session_doc = db.exam_sessions.find_one({"_id": session_id})
        if not session_doc:
            return jsonify({"error": "Exam session not found"}), 404
        db.room_availability.update_one(
            {"room_id": room_id, "session_id": session_id},
            {
                "$set": {
                    "room_id": room_id,
                    "session_id": session_id,
                    "date": session_doc.get("date"),
                    "is_available": str(payload.get("is_available", "true")).lower() != "false",
                    "reason": payload.get("reason"),
                    "updated_at": datetime.utcnow(),
                },
                "$setOnInsert": {"created_at": datetime.utcnow()},
            },
            upsert=True,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"status": "saved"})


@app.route('/seating/preview', methods=['GET'])
@login_required
def seating_preview():
    session_id = request.args.get("session_id")
    room_codes = session.get("selected_room_codes", [])
    rooms = get_rooms_by_codes(db, room_codes)
    if not session_id or not rooms:
        return jsonify({"error": "Select a session and rooms first."}), 400
    preview = preview_session_capacity(db, session_id, [str(room["_id"]) for room in rooms])
    return jsonify(
        {
            "session_id": str(preview["session"]["_id"]),
            "exam_count": preview["exam_count"],
            "total_candidates": preview["total_candidates"],
            "total_capacity": preview["total_capacity"],
            "room_count": len(preview["rooms"]),
            "warnings": preview["warnings"],
        }
    )


# here we are assigning the classname and seat num for each class
@app.route('/details', methods=['POST'])
@login_required
def details():
    if request.method == 'POST':
        items = request.form.getlist('item[]')
        if not items:
            flash('Select at least one active classroom.', 'danger')
            return redirect(url_for('classchoose'))

        rooms = get_rooms_by_codes(db, items)
        class_data = [
            {
                "class_name": room["room_name"],
                "classroom_code": room["room_code"],
                "column": int(room.get("columns") or 10),
                "rows": int(room.get("rows") or 10),
                "capacity": int(room.get("capacity") or 0),
            }
            for room in rooms
        ]
        if not class_data:
            flash('No active classrooms matched the selection.', 'danger')
            return redirect(url_for('classchoose'))

        session["selected_room_codes"] = selected_room_codes_from_request(items)

        # Compatibility export for older viewers; MongoDB remains the source of truth.
        with open('static/stuarrange.txt', 'w') as f:
            json.dump(class_data, f, indent=4)

        global filled
        filled = False
        return render_template('classdetails.html', class_data=class_data)


# here the seating is done
# only two students can sit one bench but with different subjects as exam
# -issue-:this issue may arise when there is limited class and students with same subject maybe seated nearby
# using the skeleton file stuarrange.txt the students are seated into the classroom
# the timetable/date is noted . stuarrange.txt files which is the seating arrangement is generated for each day in the timetable

@app.route('/seating', methods=['GET'])
@login_required
def seating():
    global filled
    room_codes = session.get("selected_room_codes", [])
    if not room_codes and os.path.exists('static/stuarrange.txt'):
        with open('static/stuarrange.txt', 'r') as stufiles:
            room_codes = [room_code(item.get("class_name")) for item in json.load(stufiles)]
    if not room_codes:
        flash('Choose classrooms before generating seating.', 'error')
        return redirect(url_for('classchoose'))

    rooms = get_rooms_by_codes(db, room_codes)
    if not rooms:
        flash('No active rooms found for the selected classrooms.', 'danger')
        return redirect(url_for('classchoose'))

    selected_session_id = request.args.get("session_id")
    replace = request.args.get("replace") == "1"
    if selected_session_id:
        target_sessions = [db.exam_sessions.find_one({"_id": ObjectId(selected_session_id)})]
    else:
        target_sessions = [item for item in list_session_summaries(db) if item.get("candidate_count", 0) > 0]

    target_sessions = [item for item in target_sessions if item]
    if not target_sessions:
        flash('No exam sessions with eligible candidates were found. Upload a valid timetable first.', 'danger')
        return redirect(url_for('timetable'))

    results = []
    for session_doc in target_sessions:
        try:
            result = generate_seating_for_session(
                db,
                session_doc["_id"],
                [str(room["_id"]) for room in rooms],
                generated_by=session.get("username", "admin"),
                replace=replace,
            )
            results.append((session_doc, result))
        except Exception as exc:
            results.append((session_doc, {"status": "failed", "warnings": [str(exc)], "allocated_candidates": 0}))

    completed = [result for _, result in results if result.get("status") == "completed"]
    failed = [(session_doc, result) for session_doc, result in results if result.get("status") != "completed"]
    if completed:
        filled = True
        flash('Generated seating for {} session(s).'.format(len(completed)), 'success')
    for session_doc, result in failed:
        label = "{} {} {}".format(session_doc.get("date"), session_doc.get("session_name"), session_doc.get("programme_type"))
        flash('{} failed: {}'.format(label, "; ".join(result.get("warnings", []))), 'danger')

    stats = {
        "students": students_collection.count_documents({}),
        "rooms": db.rooms.count_documents({"is_active": True}),
        "sessions": db.exam_sessions.count_documents({}),
        "exams": db.exams.count_documents({}),
        "allocations": db.seat_allocations.count_documents({"is_active": True}),
        "batches": db.generation_batches.count_documents({}),
    }
    return render_template("adminhome.html", stats=stats, generation_results=results)


@app.route('/viewseating', methods=['GET'])
@login_required
def viewseating():
    global filled
    generated_sessions = list_generated_sessions(db)
    if not generated_sessions and not filled:
        flash('Firstly generate seating', 'error')
        return render_template("adminhome.html")
    return render_template(
        'viewseating.html',
        sessions=Markup(json.dumps(generated_sessions)),
        dates=Markup(json.dumps([item["label"] for item in generated_sessions])),
    )
# Render the 'viewseating.html' template, passing the content of 'dates.txt' as the 'dates' variable
# Markup is used to mark the content as safe to render HTML tags, assuming the content contains HTML


@app.route('/viewseating/<path:name>', methods=['GET'])
@login_required
def viewseating1(name):
    global filled
    try:
        return jsonify(room_wise_allocations(db, name))
    except Exception:
        if filled:
            file_loc = 'static/stuarrange'+name+'.txt'
            if os.path.exists(file_loc):
                with open(file_loc, 'r') as file:
                    return file.read()
        flash('Firstly generate seating', 'error')
        return render_template("adminhome.html")


# Resetting everything out
@app.route('/reset', methods=['GET'])
@login_required
def reset():
    return render_template('reset.html')


@app.route('/reset/collections', methods=['GET'])
@login_required
def reset_collections():
    global filled
    if request.args.get("confirm") != "YES":
        message = "Student cleanup was not run. Add confirm=YES after taking a backup."
        return render_template('reset.html', message=message)
    filled = False
    students_collection.drop()
    db.exam_candidates.drop()
    db.seat_allocations.drop()
    initialize_exam_centric_collections(db)
    message = "Student, candidate, and allocation data has been deleted."
    return render_template('reset.html', message=message)


@app.route('/reset/users', methods=['GET'])
@login_required
def reset_users():
    if request.args.get("confirm") != "YES":
        message = "User cleanup was not run. Add confirm=YES after taking a backup."
        return render_template('reset.html', message=message)
    usercollections.drop()  # Drop the 'users' collection
    initialize_exam_centric_collections(db)
    message = "Users has been deleted."
    return render_template('reset.html', message=message)


@app.route('/reset/static', methods=['GET'])
@login_required
def reset_static():
    folder_path = 'static'
    files = os.listdir(folder_path)  # Get a list of all files in the folder
    for file in files:
        if file.startswith("stuarrange"):
            # Get the full path of the file
            file_path = os.path.join(folder_path, file)
            os.remove(file_path)  # Remove the file from the folder
    message = "Static files have been reset."
    global filled
    filled = False
    return render_template('reset.html', message=message)


@app.route('/reset/uploads', methods=['GET'])
@login_required
def reset_uploads():
    folder_path = 'uploads'
    files = os.listdir(folder_path)
    for file in files:
        file_path = os.path.join(folder_path, file)
        os.remove(file_path)
    message = "Uploads have been reset."
    return render_template('reset.html', message=message)


@app.route('/reset/timetable', methods=['GET'])
@login_required
def reset_timetable():
    global filled, dates, timetable2, timetable3, timetable4
    if request.args.get("confirm") != "YES":
        message = "Timetable cleanup was not run. Add confirm=YES after taking a backup."
        return render_template('reset.html', message=message)

    db.exam_sessions.drop()
    db.exams.drop()
    db.exam_candidates.drop()
    db.seat_allocations.drop()
    db.generation_batches.drop()
    db.room_availability.drop()
    stucollections.update_many({}, {"$unset": {"subject": "", "seatnum": ""}})
    initialize_exam_centric_collections(db)

    folder_path = 'static'
    for file in os.listdir(folder_path):
        if file.startswith("stuarrange"):
            os.remove(os.path.join(folder_path, file))

    file_path = os.path.join(folder_path, 'dates.txt')
    with open(file_path, 'w') as file:
        file.write('[]')

    dates = []
    timetable2 = None
    timetable3 = None
    timetable4 = None
    filled = False
    message = "Timetable, exam sessions, candidates, seating allocations, and generated seating files have been cleared."
    return render_template('reset.html', message=message)


@app.route('/reset/dates', methods=['GET'])
@login_required
def reset_dates():
    folder_path = 'static'
    file_path = os.path.join(folder_path, 'dates.txt')
    with open(file_path, 'w') as file:
        file.write('[]')
    message = "Dates have been reset."
    return render_template('reset.html', message=message)

# main function
if __name__ == '__main__':
    app.run(debug=app.debug, host='0.0.0.0')
