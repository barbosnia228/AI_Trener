from dataclasses import dataclass, field
from typing import List

@dataclass
class WorkoutSession:
    id: int = None
    date: str = None

    weight: float = 0.0
    rating: int = 0
    weight_feedback: str = "normal"

    sets: List[int] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)