def student_allocations_by_roll_number(db, roll_number):
    roll_text = str(roll_number).strip()
    student = db.students.find_one({"roll_number": roll_text})
    if not student:
        student = db.students.find_one({"legacy_rollnum": roll_text})
    if not student and roll_text.isdigit():
        student = db.students.find_one({"legacy_rollnum": int(roll_text)})
    if not student:
        return None, []

    allocations = list(
        db.seat_allocations.find({"student_id": student["_id"], "is_active": True}).sort(
            [("date", 1), ("start_time", 1)]
        )
    )
    results = []
    for allocation in allocations:
        exam = db.exams.find_one({"_id": allocation["exam_id"]}) or {}
        session = db.exam_sessions.find_one({"_id": allocation["exam_session_id"]}) or {}
        room = db.rooms.find_one({"_id": allocation["room_id"]}) or {}
        results.append(
            {
                "student_name": student.get("name"),
                "roll_number": student.get("roll_number"),
                "exam_code": exam.get("exam_code"),
                "subject": exam.get("subject_name"),
                "date": allocation.get("date"),
                "session": session.get("session_name") or allocation.get("session_name"),
                "start_time": allocation.get("start_time"),
                "end_time": allocation.get("end_time"),
                "programme_type": exam.get("programme_type") or session.get("programme_type"),
                "nta_level": exam.get("nta_level"),
                "classroom": room.get("room_name"),
                "seatnum": allocation.get("seat_number"),
                "seat_number": allocation.get("seat_number"),
            }
        )
    return student, results
