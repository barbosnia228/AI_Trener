import sqlite3

DB_NAME = "trainer_data.db"

def get_connection():
    """Создает подключение к базе данных."""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    # Это чтобы получать данные не списком (1, 2), а словарем {'id': 1, 'reps': 2}
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Создает таблицы при первом запуске."""
    query = '''
    CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        exercise_name TEXT,
        reps INTEGER,
        sets INTEGER,
        total_errors INTEGER,
        main_error TEXT
    )
    '''
    with get_connection() as conn:
        conn.execute(query)
        conn.commit()