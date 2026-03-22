from dataclasses import dataclass


ACCURACY_WEIGHT = 0.7
TIME_WEIGHT = 0.3

TIME_THRESHOLDS = {
    "excellent": 30.0,
    "good": 60.0,
    "pass": 120.0,
}

TIME_RATING_SCORES = {
    "excellent": 10,
    "good": 8,
    "pass": 6,
    "fail": 0,
}

TIME_RATING_LABELS = {
    "excellent": "优秀",
    "good": "良好",
    "pass": "及格",
    "fail": "不及格",
}


@dataclass(frozen=True)
class TimeEvaluation:
    rating: str
    label: str
    score: int
    excellent_threshold: float
    good_threshold: float
    pass_threshold: float


def evaluate_time(duration: float) -> TimeEvaluation:
    """Evaluate runtime against fixed thresholds."""
    excellent_threshold = TIME_THRESHOLDS["excellent"]
    good_threshold = TIME_THRESHOLDS["good"]
    pass_threshold = TIME_THRESHOLDS["pass"]

    if duration <= excellent_threshold:
        rating = "excellent"
    elif duration <= good_threshold:
        rating = "good"
    elif duration <= pass_threshold:
        rating = "pass"
    else:
        rating = "fail"

    return TimeEvaluation(
        rating=rating,
        label=TIME_RATING_LABELS[rating],
        score=TIME_RATING_SCORES[rating],
        excellent_threshold=excellent_threshold,
        good_threshold=good_threshold,
        pass_threshold=pass_threshold,
    )


def combine_weighted_score(
    accuracy_score: float,
    time_score: float,
    accuracy_weight: float = ACCURACY_WEIGHT,
    time_weight: float = TIME_WEIGHT,
) -> float:
    """Combine accuracy and runtime into a single 0-10 score."""
    total_weight = accuracy_weight + time_weight
    if total_weight <= 0:
        raise ValueError("Total score weight must be positive.")

    weighted_total = (accuracy_score * accuracy_weight) + (time_score * time_weight)
    return weighted_total / total_weight
