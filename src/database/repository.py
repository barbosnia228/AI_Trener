from .connection import get_connection
from .models import WorkoutSession
from datetime import datetime
from . import connection


class WorkoutRepository:
    def __init__(self):
        connection.init_db()

    def save_session(self, session: WorkoutSession):
        with get_connection() as conn:
            cursor = conn.cursor()

            # тренировка
            cursor.execute('''
                INSERT INTO workouts (date, weight, rating, weight_feedback)
                VALUES (?, ?, ?, ?)
            ''', (
                datetime.now().strftime("%d.%m.%Y %H:%M"),
                session.weight,
                session.rating,
                session.weight_feedback
            ))

            workout_id = cursor.lastrowid

            # подходы
            for i, reps in enumerate(session.sets, start=1):
                cursor.execute('''
                    INSERT INTO sets (workout_id, set_number, reps)
                    VALUES (?, ?, ?)
                ''', (workout_id, i, reps))

            # ошибки
            for error in session.errors:
                cursor.execute('''
                    INSERT INTO errors (workout_id, error_text)
                    VALUES (?, ?)
                ''', (workout_id, error))

            conn.commit()

    def get_history(self):
        with get_connection() as conn:
            cursor = conn.cursor()

            workouts = cursor.execute(
                "SELECT * FROM workouts ORDER BY id DESC"
            ).fetchall()

            result = []

            for w in workouts:
                sets_rows = cursor.execute(
                    "SELECT reps FROM sets WHERE workout_id=? ORDER BY set_number",
                    (w["id"],)
                ).fetchall()

                sets = [s["reps"] for s in sets_rows]

                error_rows = cursor.execute(
                    "SELECT error_text FROM errors WHERE workout_id=?",
                    (w["id"],)
                ).fetchall()

                errors = [e["error_text"] for e in error_rows]

                result.append(WorkoutSession(
                    id=w["id"],
                    date=w["date"],
                    weight=w["weight"],
                    rating=w["rating"],
                    weight_feedback=w["weight_feedback"],
                    sets=sets,
                    errors=errors
                ))

            return result