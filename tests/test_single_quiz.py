import asyncio
import sys

from tests.benchmark import QUIZ_PATH, parse_quiz, run_single_question


QUESTION_INDEX = 0
MIN_ACCURACY_SCORE = 8
DISALLOWED_TIME_RATING = "fail"


async def run_single_quiz_test() -> int:
    """Run the full pipeline against quiz.md question 1."""
    print("Starting single quiz regression test...")

    questions = parse_quiz(QUIZ_PATH)
    if len(questions) <= QUESTION_INDEX:
        raise RuntimeError(
            f"Question {QUESTION_INDEX + 1} was not found in {QUIZ_PATH}."
        )

    question = questions[QUESTION_INDEX]
    result = await run_single_question(
        question["question"],
        question["expected"],
        question_number=QUESTION_INDEX + 1,
    )

    if result["actual"].startswith("Error:"):
        raise AssertionError(f"Pipeline execution failed: {result['actual']}")

    if result["accuracy_score"] < MIN_ACCURACY_SCORE:
        raise AssertionError(
            "Single quiz regression test failed: "
            f"accuracy score {result['accuracy_score']}/10 is below "
            f"the required {MIN_ACCURACY_SCORE}/10."
        )

    if result["time_rating"] == DISALLOWED_TIME_RATING:
        raise AssertionError(
            "Single quiz regression test failed: "
            f"runtime {result['time']:.2f}s exceeded the pass threshold."
        )

    print("\nSingle quiz regression test passed.")
    print(
        f"Question: {result['question']}\n"
        f"Accuracy: {result['accuracy_score']}/10 | "
        f"Time Grade: {result['time_rating_label']} | "
        f"Final: {result['final_score']:.2f}/10"
    )
    return 0


def main() -> int:
    try:
        return asyncio.run(run_single_quiz_test())
    except Exception as exc:
        print(f"\nSingle quiz regression test failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
