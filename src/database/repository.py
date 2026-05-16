import sqlite3
import json
from datetime import datetime
from .connection import get_connection, init_db
from .models import WorkoutSession, WorkoutSet


class WorkoutRepository:
    def __init__(self):
        init_db()

    def save_session(self, session_json: str):
        """Saves workout session from JSON"""
    
        session = json.loads(session_json)
    
        with get_connection() as conn:
            cursor = conn.cursor()
    
            cursor.execute('''
                INSERT INTO workouts (date, rating, weight_feedback)
                VALUES (?, ?, ?)
            ''', (
                session.get("date", datetime.now().strftime("%d.%m.%Y %H:%M")),
                session.get("rating", 0),
                session.get("feedback", "normal")
            ))
    
            workout_id = cursor.lastrowid
    
            for i, s in enumerate(session.get("sets", []), start=1):
                cursor.execute('''
                    INSERT INTO sets (workout_id, set_number, reps, weight)
                    VALUES (?, ?, ?, ?)
                ''', (
                    workout_id,
                    i,
                    s["reps"],
                    s["weight"]
                ))
    
            for error in session.get("errors", []):
                cursor.execute('''
                    INSERT INTO errors (workout_id, error_text)
                    VALUES (?, ?)
                ''', (
                    workout_id,
                    error
                ))
    
            conn.commit()

    def get_full_analytics_json(self) -> str:
        """Returns JSON containing global stats, chart data, and full history"""
        with get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM workouts ORDER BY id ASC").fetchall()

            history_list = []
            chart_data = {"labels": [], "volumes": [], "max_weights": []}
            total_reps = 0
            all_time_max = 0

            for r in rows:
                details = self._get_workout_details(cursor, r)

                total_reps += details["summary"]["reps_count"]
                if details["summary"]["max_weight"] > all_time_max:
                    all_time_max = details["summary"]["max_weight"]

                chart_data["labels"].append(r["date"].split(" ")[0])
                chart_data["volumes"].append(details["summary"]["volume"])
                chart_data["max_weights"].append(details["summary"]["max_weight"])

                history_list.append(details)

            result = {
                "overall": {
                    "total_workouts": len(history_list),
                    "total_reps": total_reps,
                    "all_time_max": all_time_max
                },
                "charts": chart_data,
                "history": list(reversed(history_list))
            }
            return json.dumps(result, ensure_ascii=False, indent=4)

    def get_last_session_json(self) -> str:
        """Returns JSON for the most recent workout session"""
        with get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT * FROM workouts ORDER BY id DESC LIMIT 1").fetchone()

            if not row:
                return json.dumps({"error": "No sessions found"}, ensure_ascii=False)

            result = self._get_workout_details(cursor, row)
            return json.dumps(result, ensure_ascii=False, indent=4)

    def get_sessions_by_date_json(self, date_str: str) -> str:
        """Returns JSON list of sessions for a specific date (e.g. '15.05.2024')"""
        with get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT * FROM workouts WHERE date LIKE ? ORDER BY id DESC",
                (f"{date_str}%",)
            ).fetchall()

            results = [self._get_workout_details(cursor, r) for r in rows]
            return json.dumps(results, ensure_ascii=False, indent=4)

    def _get_workout_details(self, cursor, row) -> dict:
        """Internal helper to aggregate all data for a single workout row"""
        w_id = row["id"]

        sets_rows = cursor.execute(
            "SELECT reps, weight FROM sets WHERE workout_id=? ORDER BY set_number", (w_id,)
        ).fetchall()
        sets = [{"reps": s["reps"], "weight": s["weight"]} for s in sets_rows]

        errors = [e["error_text"] for e in cursor.execute(
            "SELECT error_text FROM errors WHERE workout_id=?", (w_id,)).fetchall()]

        volume = sum(s["reps"] * s["weight"] for s in sets)
        max_w = max((s["weight"] for s in sets), default=0)
        reps_count = sum(s["reps"] for s in sets)

        return {
            "id": w_id,
            "date": row["date"],
            "rating": row["rating"],
            "feedback": row["weight_feedback"],
            "sets": sets,
            "errors": errors,
            "summary": {
                "volume": volume,
                "max_weight": max_w,
                "reps_count": reps_count
            }
        }
