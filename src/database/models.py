from dataclasses import dataclass, field
from typing import List, Union

@dataclass
class WorkoutSet:
    reps: int
    weight: float

@dataclass
class WorkoutSession:
    id: int = None
    date: str = None
    rating: int = 0
    weight_feedback: str = "normal"
    sets: List[Union[WorkoutSet, dict]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)