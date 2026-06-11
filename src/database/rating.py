def calculate_rating(
    actual_sets: list[dict],
    target_sets: int,
    target_reps: int,
    errors: list[str]
) -> int:
    rating = 10

    rating -= len(errors)

    for s in actual_sets:
        missing = max(0, target_reps - s["reps"])
        rating -= missing * 0.2

    missing_sets = max(0, target_sets - len(actual_sets))
    rating -= missing_sets * 2

    return max(0, round(rating))