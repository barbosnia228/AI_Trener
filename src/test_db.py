import json
from database.repository import WorkoutRepository
from database.models import WorkoutSession, WorkoutSet


def main():
    repo = WorkoutRepository()

    # 1. Створюємо першу сесію
    # Тепер вага вказується для кожного підходу окремо через WorkoutSet
    session1 = WorkoutSession(
        rating=9,
        weight_feedback="good",
        sets=[
            WorkoutSet(reps=12, weight=50.0),
            WorkoutSet(reps=10, weight=55.0),
            WorkoutSet(reps=8, weight=60.0)
        ],
        errors=["Back arch", "Too fast"]
    )
    repo.save_session(session1)

    # 2. Створюємо другу сесію
    session2 = WorkoutSession(
        rating=10,
        weight_feedback="excellent",
        sets=[
            WorkoutSet(reps=10, weight=70.0),
            WorkoutSet(reps=10, weight=70.0),
            WorkoutSet(reps=10, weight=70.0)
        ],
        errors=["None"]
    )
    repo.save_session(session2)

    print("Sessions Saved!\n")

    # 3. Отримуємо аналітику в форматі JSON
    json_data = repo.get_full_analytics_json()

    # Парсимо JSON назад у словник для виводу
    data = json.loads(json_data)

    print("--- WORKOUT HISTORY ---")
    for w in data["history"]:
        # Форматуємо підходи для гарного виводу: "10кг x 12, 12кг x 10..."
        sets_display = ", ".join([f"{s['weight']}kg x {s['reps']}" for s in w['sets']])

        print(f"""
ID: {w['id']}
Date: {w['date']}
Rate: {w['rating']}
Feedback: {w['feedback']}

Sets (Weight x Reps): {sets_display}
Summary: Vol: {w['summary']['volume']}kg | Max: {w['summary']['max_weight']}kg
Mistakes: {", ".join(w['errors'])}
-------------------------""")

    # 4. Демонстрація загальної статистики для фронтенда
    overall = data["overall"]
    print(f"\nGLOBAL STATS:")
    print(f"Total Workouts: {overall['total_workouts']}")
    print(f"All Time Max Weight: {overall['all_time_max']} kg")


if __name__ == "__main__":
    main()