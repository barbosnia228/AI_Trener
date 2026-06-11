import sqlite3
import json
from datetime import datetime
from .connection import get_connection, init_db
from .models import WorkoutSession, WorkoutSet


class WorkoutRepository:
    """
    Data-access layer for workout sessions.

    Wraps all SQLite read/write operations for the ``workouts``, ``sets``,
    and ``errors`` tables. Every public method accepts or returns plain JSON
    strings so that callers (e.g. an AI agent or HTTP handler) stay decoupled
    from the database schema.

    The database is initialised automatically on construction via ``init_db()``,
    so no separate setup step is required.
    """
    def __init__(self):
        init_db()

    def save_session(self, session_json: str):
        """
        Persists a workout session from a JSON string to the database.

        Parses the input, inserts a row into ``workouts``, then inserts one row
        per set into ``sets`` and one row per form error into ``errors``.
        All three inserts are wrapped in a single transaction — either all
        succeed or none are committed.

        Parameters
        ----------
        session_json : str
            JSON string with the following optional keys:

            - ``date`` *(str)* — session datetime; defaults to the current
              time formatted as ``'DD.MM.YYYY HH:MM'`` if omitted.
            - ``rating`` *(int)* — quality score 0–10; defaults to ``0``.
            - ``feedback`` *(str)* — weight recommendation; defaults to ``'normal'``.
            - ``sets`` *(list of dict)* — each dict must have ``'reps'`` *(int)*
              and ``'weight'`` *(float)*; set order is derived from list position.
            - ``errors`` *(list of str)* — form error descriptions to attach
              to the session.
        """
    
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
        """
        Aggregates all workout history into a single analytics payload.

        Iterates over every session in chronological order and computes:

        - **overall** — lifetime totals: session count, total reps, and all-time max weight.
        - **charts** — parallel lists of labels, total volumes, and max weights per session,
          intended for direct use in a frontend chart (e.g. Chart.js or Recharts).
        - **history** — full session detail list (newest first), each entry produced
          by :py:meth:`_get_workout_details`.

        Returns
        -------
        str
            Pretty-printed JSON with keys ``overall``, ``charts``, and ``history``.
        """
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
        """
        Returns the most recently saved workout session as JSON.

        Queries the ``workouts`` table for the row with the highest ``id``
        and delegates full detail assembly to :py:meth:`_get_workout_details`.

        Returns
        -------
        str
            Pretty-printed JSON with session fields (see :py:meth:`_get_workout_details`).
            If no sessions exist, returns ``{"error": "No sessions found"}``.
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT * FROM workouts ORDER BY id DESC LIMIT 1").fetchone()

            if not row:
                return json.dumps({"error": "No sessions found"}, ensure_ascii=False)

            result = self._get_workout_details(cursor, row)
            return json.dumps(result, ensure_ascii=False, indent=4)

    def get_sessions_by_date_json(self, date_str: str) -> str:
        """
        Returns all workout sessions recorded on a given date.

        Performs a ``LIKE`` prefix match on the ``date`` column, so the caller
        only needs to provide the date portion (e.g. ``'15.05.2024'``) without
        worrying about the time component.  Multiple sessions on the same day
        are returned newest-first.

        Parameters
        ----------
        date_str : str
            Date string in ``'DD.MM.YYYY'`` format.

        Returns
        -------
        str
            Pretty-printed JSON array of session detail dicts.
            Returns an empty array (``[]``) if no sessions match.
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT * FROM workouts WHERE date LIKE ? ORDER BY id DESC",
                (f"{date_str}%",)
            ).fetchall()

            results = [self._get_workout_details(cursor, r) for r in rows]
            return json.dumps(results, ensure_ascii=False, indent=4)

    def _get_workout_details(self, cursor, row) -> dict:
        """
        Assembles a complete detail dict for a single workout database row.

        Fetches the associated sets and errors from their respective tables,
        then computes derived metrics. Intended as a private helper called
        from all public query methods to keep result formatting consistent.

        Parameters
        ----------
        cursor : sqlite3.Cursor
            An active cursor on the current connection, used to run sub-queries.
        row : sqlite3.Row
            A row from the ``workouts`` table; must expose ``id``, ``date``,
            ``rating``, and ``weight_feedback`` by column name.

        Returns
        -------
        dict
            A dict with the following keys:

            - ``id`` — workout primary key.
            - ``date`` — session datetime string.
            - ``rating`` — session quality score (0–10).
            - ``feedback`` — weight adjustment recommendation.
            - ``sets`` — list of ``{'reps': int, 'weight': float}`` dicts.
            - ``errors`` — list of form-error description strings.
            - ``summary`` — nested dict with ``volume`` (total kg·reps),
              ``max_weight`` (heaviest set weight), and ``reps_count`` (total reps).
        """
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

    def get_weight_recommendation(self) -> str:
        """
        Derives a weight adjustment recommendation based on the last session.

        Looks up the most recent workout and applies the following rules
        (checked in order):

        - **``'increase'``** — rating ≥ 8 *and* total reps ≥ 27; the athlete
          handled the load well enough to progress.
        - **``'decrease'``** — rating ≤ 5 *or* total reps < 20; the session
          was too difficult or incomplete.
        - **``'normal'``** — all other cases; keep the current weight.

        Returns
        -------
        str
            One of ``'increase'``, ``'decrease'``, or ``'normal'``.
            Returns ``'normal'`` if the database contains no sessions yet.
        """
        with get_connection() as conn:
            cursor = conn.cursor()

            row = cursor.execute("""
                SELECT id, rating
                FROM workouts
                ORDER BY id DESC
                LIMIT 1
            """).fetchone()

            if not row:
                return "normal"

            workout_id = row["id"]
            rating = row["rating"]

            reps = cursor.execute("""
                SELECT SUM(reps) as total
                FROM sets
                WHERE workout_id = ?
            """, (workout_id,)).fetchone()["total"] or 0

            if rating >= 8 and reps >= 27:
                return "increase"

            if rating <= 5 or reps < 20:
                return "decrease"

            return "normal"