from database.repository import WorkoutRepository
from database.models import WorkoutSession


def main():
    repo = WorkoutRepository()

    session = WorkoutSession(
        weight=85.0,
        rating=9,
        weight_feedback="good",
        sets=[12, 10, 8],
        errors=["Back arch", "Too fast"]
    )

    repo.save_session(session)

    print("Сохранено!\n")

    history = repo.get_history()

    for w in history:
        print(f"""
ID: {w.id}
Дата: {w.date}
Вес: {w.weight}
Оценка: {w.rating}
Фидбек: {w.weight_feedback}

Подходы: {w.sets}
Ошибки: {w.errors}
-------------------------
""")


if __name__ == "__main__":
    main()