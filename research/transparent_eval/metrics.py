"""Grouped evaluation metrics. Abstentions are reported, never dropped silently."""
from collections import defaultdict


def ordinal_metrics(reference, prediction, high_grade=2):
    if len(reference) != len(prediction) or not reference:
        raise ValueError("nonempty equally sized sequences required")
    if any(type(x) is not int or x not in range(4) for x in reference):
        raise ValueError("reference grades must be integers 0..3")
    if any(x is not None and (type(x) is not int or x not in range(4)) for x in prediction):
        raise ValueError("predictions must be None or integers 0..3")
    if type(high_grade) is not int or high_grade not in (1, 2, 3):
        raise ValueError("high_grade must be 1, 2 or 3")
    matrix = [[0] * 5 for _ in range(4)]  # Final column is abstention.
    for y, p in zip(reference, prediction):
        matrix[y][4 if p is None else p] += 1
    high = sum(y >= high_grade for y in reference)
    low = len(reference) - high
    accepted = [(y, p) for y, p in zip(reference, prediction) if p is not None]
    low_high = sum(y >= high_grade and p < high_grade for y, p in accepted)
    abstain_high = sum(y >= high_grade and p is None for y, p in zip(reference, prediction))
    ratio = lambda a, b: a / b if b else None
    return {"n": len(reference), "confusion_with_abstention_column": matrix,
            "coverage": len(accepted) / len(reference),
            "accuracy_all_cases": sum(y == p for y, p in accepted) / len(reference),
            "ordinal_error_accepted": ratio(sum(abs(y-p) for y,p in accepted), len(accepted)),
            "high_grade_underestimation_rate": ratio(sum(y >= high_grade and p < y for y,p in accepted), high),
            "high_grade_threshold_miss_rate": ratio(low_high, high),
            "high_grade_abstention_rate": ratio(abstain_high, high),
            "high_grade_unresolved_or_missed_rate": ratio(low_high + abstain_high, high),
            "high_grade_recall": ratio(sum(y >= high_grade and p >= high_grade for y,p in accepted), high),
            "false_alarm_rate": ratio(sum(y < high_grade and p >= high_grade for y,p in accepted), low),
            "false_alarm_or_abstention_on_low_rate": ratio(
                sum(y < high_grade and (p is None or p >= high_grade) for y,p in zip(reference,prediction)), low)}


def validate_split(rows):
    """A correlated engineering unit/event may not span development/test partitions."""
    groups = defaultdict(set)
    seen = set()
    for row in rows:
        sid = row["sample_id"]
        if not sid or sid in seen:
            raise ValueError("duplicate/empty sample_id")
        seen.add(sid)
        if row["split"] not in ("development", "calibration", "test"):
            raise ValueError("unknown split")
        if not row["group_ids"] or any(not g for g in row["group_ids"]):
            raise ValueError("independence groups required")
        for group in row["group_ids"]:
            groups[group].add(row["split"])
    leakage = {g: sorted(s) for g, s in groups.items() if len(s) > 1}
    if leakage:
        raise ValueError(f"cross-partition leakage: {leakage}")
    return {"n_samples": len(rows), "n_groups": len(groups)}
