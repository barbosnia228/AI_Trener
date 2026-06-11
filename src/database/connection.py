import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "data", "trainer_data.db"))

def get_connection():
    """
    Opens and returns a new SQLite connection to the application database.

    The connection uses ``sqlite3.Row`` as its row factory, so all query results
    are accessible both by column index and by column name (e.g. ``row['date']``).
    ``check_same_thread=False`` is set to allow the connection to be used from
    threads other than the one that created it.

    Returns
    -------
    sqlite3.Connection
        An open connection to ``trainer_data.db``.
    """
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Creates the database schema if it does not already exist.

    Runs a single ``executescript`` call that issues ``CREATE TABLE IF NOT EXISTS``
    statements for the three core tables:

    - **workouts** — one row per session; stores date, rating, and weight feedback.
    - **sets** — one row per set; linked to ``workouts`` via ``workout_id``;
      stores set order, rep count, and weight used.
    - **errors** — one row per form error; linked to ``workouts`` via ``workout_id``;
      stores a human-readable error description.

    Safe to call on every application start — existing data is never modified.
    """
    with get_connection() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            rating INTEGER,
            weight_feedback TEXT
        );

        CREATE TABLE IF NOT EXISTS sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_id INTEGER,
            set_number INTEGER,
            reps INTEGER,
            weight REAL,
            FOREIGN KEY (workout_id) REFERENCES workouts(id)
        );

        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_id INTEGER,
            error_text TEXT,
            FOREIGN KEY (workout_id) REFERENCES workouts(id)
        );
        ''')