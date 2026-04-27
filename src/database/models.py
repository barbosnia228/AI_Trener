from dataclasses import dataclass

@dataclass
class WorkoutSession:
    id: int = None
    date: str = None
    exercise_name: str = "Squats"  # По умолчанию одно упр.
    reps: int = 0
    sets: int = 0
    total_errors: int = 0
    main_error: str = "None"

    def to_dict(self):
        return {
            "date": self.date,
            "exercise": self.exercise_name,
            "reps": self.reps,
            "sets": self.sets,
            "errors": self.total_errors,
            "top_error": self.main_error
        }