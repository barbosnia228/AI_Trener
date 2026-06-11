from dataclasses import dataclass, field
from typing import List, Union

@dataclass
class WorkoutSet:
    """
    Represents a single set within a workout session.

    Attributes
    ----------
    reps : int
        Number of repetitions performed in this set.
    weight : float
        Weight used during this set, in kilograms.
    """
    reps: int
    weight: float

@dataclass
class WorkoutSession:
    """
    Represents a complete workout session with all associated metadata.

    Attributes
    ----------
    id : int, optional
        Unique session identifier assigned by the database on insert.
    date : str, optional
        Session date and time as a formatted string (e.g. ``'15.05.2024 10:30'``).
    rating : int
        Overall session quality score in the range 0–10.
        Calculated by ``calculate_rating()`` based on completed sets, reps, and errors.
    weight_feedback : str
        Weight adjustment recommendation for the next session.
        One of ``'increase'``, ``'decrease'``, or ``'normal'``.
    sets : list of WorkoutSet or dict
        Ordered list of sets performed during the session.
        May contain either ``WorkoutSet`` dataclass instances or raw dicts
        (as returned from the database layer).
    errors : list of str
        Human-readable descriptions of form errors detected during the session.
        Each error reduces the session rating by 1 point.
    """
    id: int = None
    date: str = None
    rating: int = 0
    weight_feedback: str = "normal"
    sets: List[Union[WorkoutSet, dict]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)