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

    session = WorkoutSession(
        weight=75.0,
        rating=10,
        weight_feedback="good",
        sets=[10, 10, 10],
        errors=["Too fast"]
    )

    repo.save_session(session)

    print("Saved!\n")

    history = repo.get_history()

    for w in history:
        print(f"""
ID: {w.id}
Date: {w.date}
Weight: {w.weight}
Rate: {w.rating}
Weight Feedback: {w.weight_feedback}

Sets: {w.sets}
Mistakes: {w.errors}
-------------------------
""")


if __name__ == "__main__":
    main()
