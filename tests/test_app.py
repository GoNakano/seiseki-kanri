import os
import sqlite3
import tempfile
import unittest

TEST_DIR = tempfile.TemporaryDirectory()
os.environ["FLASK_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["SKIP_DB_INIT"] = "1"
os.environ["DATABASE_PATH"] = os.path.join(TEST_DIR.name, "test.db")

from app import DB_FILE, app, calculate_gpa_gps, get_user_statistics, initialize_database

app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
initialize_database()


class AppSmokeTest(unittest.TestCase):
    def setUp(self):
        conn = sqlite3.connect(DB_FILE)
        conn.execute("DELETE FROM review_reports")
        conn.execute("DELETE FROM course_reviews")
        conn.execute("DELETE FROM grades")
        conn.execute("DELETE FROM users")
        conn.commit()
        conn.close()
        initialize_database()
        self.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        TEST_DIR.cleanup()

    def register_user(self, user_id="testuser", nickname="Test User"):
        response = self.client.post(
            "/register",
            data={
                "user_id": user_id,
                "nickname": nickname,
                "password": "password123",
                "password2": "password123",
                "current_year": "1",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_health_check_is_public(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_demo_data_requires_login_and_is_idempotent(self):
        response = self.client.post("/api/load_demo_data")
        self.assertEqual(response.status_code, 302)

        self.register_user("demouser", "Demo User")
        self.assertEqual(self.client.get("/").status_code, 200)
        response = self.client.post("/api/load_demo_data")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["count"], 8)

        courses = self.client.get("/api/get_courses").get_json()
        self.assertEqual(len(courses), 8)

        response = self.client.post("/api/load_demo_data")
        self.assertEqual(response.status_code, 409)

    def test_csv_export_contains_only_current_users_courses(self):
        self.register_user("csvuser", "CSV User")
        self.client.post(
            "/api/add_course",
            json={
                "year": 2026,
                "semester": "Spring",
                "name": "Web Application Development",
                "credits": 2,
                "grade": "A",
                "category": "Unclassified",
                "memo": "smoke test",
            },
        )

        response = self.client.get("/api/export_courses")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)
        self.assertIn("Web Application Development", response.get_data(as_text=True))

        self.client.get("/logout")
        self.register_user("othercsv", "Other CSV")
        response = self.client.get("/api/export_courses")
        self.assertNotIn("Web Application Development", response.get_data(as_text=True))

    def test_courses_are_isolated_between_users(self):
        self.register_user("firstuser", "First User")
        self.client.post(
            "/api/add_course",
            json={
                "year": 2026,
                "semester": "Spring",
                "name": "Private Course",
                "credits": 2,
                "grade": "A",
                "category": "Unclassified",
                "memo": "",
            },
        )
        self.client.get("/logout")

        self.register_user("seconduser", "Second User")
        courses = self.client.get("/api/get_courses").get_json()
        self.assertEqual(courses, [])

    def test_public_reviews_are_anonymous_and_reportable(self):
        self.register_user("reviewone", "Review One")
        response = self.client.post(
            "/api/reviews",
            json={
                "course_name": "Web Application Development",
                "course_code": "CS101",
                "instructor": "担当者A",
                "term": "2026年度 春学期",
                "difficulty": 2,
                "workload": 3,
                "attendance": "一部出席",
                "assessment": "試験70%・レポート30%",
                "comment": "課題の説明が明確で、復習しやすい授業でした。",
                "is_public": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        review_id = response.get_json()["review_id"]

        self.client.get("/logout")
        self.register_user("reviewtwo", "Review Two")
        response = self.client.get("/api/reviews?query=CS101")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()[0]["review_count"], 1)

        detail = self.client.get(
            "/api/reviews/detail?course_key=code:cs101"
        )
        self.assertEqual(detail.status_code, 200)
        comment = detail.get_json()["comments"][0]
        self.assertEqual(comment["comment"], "課題の説明が明確で、復習しやすい授業でした。")
        self.assertNotIn("user_id", comment)

        response = self.client.post(f"/api/reviews/{review_id}/report")
        self.assertEqual(response.status_code, 200)
        detail = self.client.get(
            "/api/reviews/detail?course_key=code:cs101"
        )
        self.assertEqual(detail.status_code, 404)

    def test_private_reviews_are_not_listed_publicly(self):
        self.register_user("privateuser", "Private User")
        response = self.client.post(
            "/api/reviews",
            json={
                "course_name": "Private Course",
                "term": "2026年度",
                "difficulty": 4,
                "workload": 4,
                "attendance": "毎回出席",
                "comment": "自分用のメモです。",
                "is_public": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        mine = self.client.get("/api/reviews/mine")
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(len(mine.get_json()), 1)
        self.assertFalse(mine.get_json()[0]["is_public"])
        response = self.client.get("/api/reviews?query=Private")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_weighted_gpa_and_earned_credits_with_dummy_grades(self):
        self.register_user("gpauser", "GPA User")
        conn = sqlite3.connect(DB_FILE)
        user_id = conn.execute(
            "SELECT id FROM users WHERE user_id = ?", ("gpauser",)
        ).fetchone()[0]
        conn.executemany(
            "INSERT INTO grades (year, name, credits, grade, user_id) VALUES (?, ?, ?, ?, ?)",
            [
                (2026, "Course A", 2, "A", user_id),
                (2026, "Course F", 1, "F", user_id),
                (2026, "Course A+", 2, "A+", user_id),
                (None, "Year Unknown", 1, "B", user_id),
                (2026, "Unsupported Grade", 2, "S", user_id),
            ],
        )
        conn.commit()
        conn.close()

        # F and unknown-year courses affect GPA; unsupported grades do not.
        self.assertEqual(calculate_gpa_gps(user_id), (3.5, 21.0, 4))
        stats = get_user_statistics(user_id)
        self.assertEqual(stats["yearly_stats"], [
            {"year": 2026, "courses": 3, "credits": 4.0, "avg_gpa": 3.6}
        ])
        self.assertEqual(
            {row["grade"] for row in stats["grade_distribution"]},
            {"A+", "A", "B", "F"},
        )

    def test_campus_html_preview_parses_dummy_course(self):
        self.register_user("htmluser", "HTML User")
        html = """<table class="campusTable">
            <tr><th>区分</th><th>科目名</th></tr>
            <tr><td>未分類</td><td>53012 テスト科目 *</td>
                <td></td><td></td><td>2.0</td><td>A</td>
                <td>2026</td><td>春学期</td></tr>
        </table>"""
        response = self.client.post("/api/parse_campus_html", json={"html": html})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(len(payload["courses"]), 1)
        course = payload["courses"][0]
        self.assertEqual(course["name"], "テスト科目")
        self.assertEqual(course["credits"], 2.0)
        self.assertEqual(course["grade"], "A")
        self.assertEqual(course["year"], 2026)

    def test_campus_html_preview_rejects_missing_table(self):
        self.register_user("badhtml", "Bad HTML User")
        response = self.client.post("/api/parse_campus_html", json={"html": ""})
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            "/api/parse_campus_html", json={"html": "<div>no table</div>"}
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
