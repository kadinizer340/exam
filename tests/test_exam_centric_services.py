import unittest

from services.exam_service import build_candidate_filter, session_warnings
from services.import_service import normalize_optional_int
from services.room_service import room_code, room_document, validate_capacity, validate_room_dimensions
from services.seating_service import interleave_candidate_groups, room_seats
from utils.time_utils import calculate_end_time, default_start_time_for_session, time_ranges_overlap
from utils.validation import normalize_programme_type, parse_nta_level, split_multi_value


class ExamCentricServiceTests(unittest.TestCase):
    def test_end_time_calculation(self):
        self.assertEqual(calculate_end_time("08:00", 180), "11:00")
        self.assertEqual(calculate_end_time("13:00", 150), "15:30")

    def test_default_session_start_times(self):
        self.assertEqual(default_start_time_for_session("Morning"), "08:00")
        self.assertEqual(default_start_time_for_session("Afternoon"), "13:00")
        self.assertEqual(default_start_time_for_session("Night"), "18:00")

    def test_time_overlap_detection(self):
        self.assertTrue(time_ranges_overlap("08:00", "11:00", "10:30", "12:00"))
        self.assertFalse(time_ranges_overlap("08:00", "11:00", "11:00", "13:00"))

    def test_nta_level_validation(self):
        self.assertEqual(parse_nta_level("NTA Level 6"), 6)
        with self.assertRaises(ValueError):
            parse_nta_level(9)

    def test_programme_type_normalization(self):
        self.assertEqual(normalize_programme_type("degree"), "Bachelor")
        self.assertEqual(normalize_programme_type("diploma"), "Diploma")

    def test_session_programme_warning(self):
        self.assertEqual(session_warnings("Morning", "Bachelor"), [])
        self.assertTrue(session_warnings("Afternoon", "Bachelor"))

    def test_room_seat_numbering_is_unique(self):
        room = {"rows": 2, "columns": 4}
        seats = list(room_seats(room))
        self.assertEqual(len(seats), 8)
        self.assertEqual(len({seat["seat_number"] for seat in seats}), 8)
        self.assertEqual(seats[0]["seat_number"], "A-01")
        self.assertEqual(seats[-1]["seat_number"], "B-04")

    def test_room_validation_and_code(self):
        self.assertEqual(room_code("ADM 303"), "ADM303")
        self.assertEqual(validate_room_dimensions("2", "3"), (2, 3))
        with self.assertRaises(ValueError):
            validate_room_dimensions(0, 3)

    def test_classroom_capacity_minimum(self):
        self.assertEqual(validate_capacity(100), 100)
        self.assertEqual(validate_capacity("120.0"), 120)
        with self.assertRaises(ValueError):
            validate_capacity(80)

    def test_default_room_seed_uses_operational_capacity_floor(self):
        room = room_document({"room_name": "ADM 305", "building": "Administration Block", "rows": 7, "columns": 3})
        self.assertEqual(room["legacy_layout_capacity"], 21)
        self.assertEqual(room["capacity"], 100)

    def test_room_seats_use_database_capacity(self):
        seats = list(room_seats({"rows": 2, "columns": 4, "capacity": 100}))
        self.assertEqual(len(seats), 100)
        self.assertEqual(len({seat["seat_number"] for seat in seats}), 100)

    def test_candidate_interleaving_mixes_exams(self):
        groups = [
            {"exam": {"exam_code": "A"}, "candidates": [{"exam": "A", "n": index} for index in range(3)]},
            {"exam": {"exam_code": "B"}, "candidates": [{"exam": "B", "n": index} for index in range(2)]},
        ]
        ordered = interleave_candidate_groups(groups)
        pairs = list(zip(ordered, ordered[1:]))
        adjacent_same = sum(1 for left, right in pairs if left["exam"] == right["exam"])
        self.assertLess(adjacent_same, len(pairs))

    def test_capacity_shortage_math(self):
        room = {"rows": 1, "columns": 2}
        shortage = 3 - len(list(room_seats(room)))
        self.assertEqual(shortage, 1)

    def test_shared_exam_candidate_filter(self):
        exam = {"programme_type": "Bachelor", "nta_level": 7}
        candidate_filter = build_candidate_filter(exam, ["Computer Science", "BIT-2A"])
        self.assertEqual(candidate_filter["programme_type"], "Bachelor")
        self.assertEqual(candidate_filter["nta_level"], 7)
        self.assertEqual(len(candidate_filter["$or"]), 3)

    def test_multi_value_group_split(self):
        self.assertEqual(split_multi_value("Computer Science, IT, Business IT"), ["Computer Science", "IT", "Business IT"])

    def test_optional_duration_accepts_excel_numeric_shapes(self):
        self.assertEqual(normalize_optional_int(120, "duration_minutes"), 120)
        self.assertEqual(normalize_optional_int(120.0, "duration_minutes"), 120)
        self.assertEqual(normalize_optional_int("120", "duration_minutes"), 120)
        self.assertEqual(normalize_optional_int("120.0", "duration_minutes"), 120)
        self.assertIsNone(normalize_optional_int("", "duration_minutes"))
        self.assertIsNone(normalize_optional_int(None, "duration_minutes"))

    def test_optional_duration_rejects_fractional_values(self):
        with self.assertRaises(ValueError):
            normalize_optional_int("120.5", "duration_minutes")


if __name__ == "__main__":
    unittest.main()
