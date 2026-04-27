from database.repository import WorkoutRepository
from database.models import WorkoutSession

def main():
    repo = WorkoutRepository()

    # 🔹 создаем тренировку
    session = WorkoutSession(
        exercise_name="Push-ups",
        reps=15,
        sets=3,
        total_errors=2,
        main_error="Bad form"
    )

    # 🔹 сохраняем в базу
    repo.save_session(session)
    print("Тренировка сохранена!\n")

    # 🔹 получаем историю
    history = repo.get_history()

    print("История тренировок:")
    for item in history:
        print(f"""
ID: {item.id}
Дата: {item.date}
Упражнение: {item.exercise_name}
Повторения: {item.reps}
Подходы: {item.sets}
Ошибки: {item.total_errors}
Главная ошибка: {item.main_error}
-------------------------
""")

if __name__ == "__main__":
    main()