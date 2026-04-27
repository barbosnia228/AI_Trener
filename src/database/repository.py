from .connection import get_connection
from .models import WorkoutSession
from datetime import datetime


class WorkoutRepository:
    def __init__(self):
        # При создании репозитория сразу проверим, есть ли таблицы
        from . import connection
        connection.init_db()

    def save_session(self, session: WorkoutSession):
        """Сохраняет результат тренировки в базу."""
        query = '''
        INSERT INTO workouts (date, exercise_name, reps, sets, total_errors, main_error)
        VALUES (?, ?, ?, ?, ?, ?)
        '''
        date_str = datetime.now().strftime("%d.%m.%Y %H:%M")

        with get_connection() as conn:
            conn.execute(query, (
                date_str,
                session.exercise_name,
                session.reps,
                session.sets,
                session.total_errors,
                session.main_error
            ))
            conn.commit()

    def get_history(self):
        """Возвращает все тренировки для страницы статистики."""
        query = "SELECT * FROM workouts ORDER BY id DESC"

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()

            # Превращаем строки из базы обратно в объекты WorkoutSession
            history = []
            for row in rows:
                history.append(WorkoutSession(
                    id=row['id'],
                    date=row['date'],
                    exercise_name=row['exercise_name'],
                    reps=row['reps'],
                    sets=row['sets'],
                    total_errors=row['total_errors'],
                    main_error=row['main_error']
                ))
            return history