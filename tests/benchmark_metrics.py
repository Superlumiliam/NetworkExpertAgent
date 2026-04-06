from dataclasses import dataclass


CONCLUSION_WEIGHT = 0.4
SOURCE_WEIGHT = 0.2
CONFIDENCE_WEIGHT = 0.2
TIME_WEIGHT = 0.2

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
    conclusion_score: float,
    source_score: float,
    confidence_score: float,
    time_score: float,
    conclusion_weight: float = CONCLUSION_WEIGHT,
    source_weight: float = SOURCE_WEIGHT,
    confidence_weight: float = CONFIDENCE_WEIGHT,
    time_weight: float = TIME_WEIGHT,
) -> float:
    """Combine structured-answer metrics and runtime into a single 0-10 score."""
    total_weight = conclusion_weight + source_weight + confidence_weight + time_weight
    if total_weight <= 0:
        raise ValueError("Total score weight must be positive.")

    weighted_total = (
        (conclusion_score * conclusion_weight)
        + (source_score * source_weight)
        + (confidence_score * confidence_weight)
        + (time_score * time_weight)
    )
    return weighted_total / total_weight
