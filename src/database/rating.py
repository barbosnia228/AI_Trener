def calculate_rating(
    actual_sets: list[dict],
    target_sets: int,
    target_reps: int,
    errors: list[str]
) -> int:
    """
    Calculates a workout quality score on a 0–10 scale.

    Starts at a perfect score of 10 and applies the following deductions:

    - **–1 per form error** detected during the session.
    - **–0.2 per missing rep** in each set (i.e. for each rep below ``target_reps``).
    - **–2 per missing set** (i.e. for each set below ``target_sets``).

    The final score is clamped to a minimum of 0 and rounded to the nearest integer.

    Parameters
    ----------
    actual_sets : list of dict
        Sets that were actually performed. Each dict must contain a ``'reps'`` key
        with the number of repetitions completed.
    target_sets : int
        The planned number of sets for this session.
    target_reps : int
        The planned number of repetitions per set.
    errors : list of str
        Form errors detected during the session; each entry reduces the score by 1.

    Returns
    -------
    int
        Session quality score in the range 0–10 (inclusive).
    """
    rating = 10

    rating -= len(errors)

    for s in actual_sets:
        missing = max(0, target_reps - s["reps"])
        rating -= missing * 0.2

    missing_sets = max(0, target_sets - len(actual_sets))
    rating -= missing_sets * 2

    return max(0, round(rating))