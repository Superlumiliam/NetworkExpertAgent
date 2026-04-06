import asyncio

from tests.benchmark import QUIZ_PATH, parse_quiz, run_single_question


MIN_CONCLUSION_SCORE = 8
MIN_SOURCE_SCORE = 6
MIN_CONFIDENCE_SCORE = 6
MIN_FINAL_SCORE = 7
FAIL_TIME_RATING = "fail"


async def main() -> int:
    questions = parse_quiz(QUIZ_PATH)
    if not questions:
        print("No quiz questions found.")
        return 1

    first_question = questions[0]
    result = await run_single_question(
        first_question["question"],
        first_question["expected"],
        question_number=1,
    )

    if str(result["actual"]).startswith("Error:"):
        print("Single quiz regression failed: main flow returned an error.")
        return 1

    if result["conclusion_score"] < MIN_CONCLUSION_SCORE:
        print(
            "Single quiz regression failed: "
            f"conclusion score {result['conclusion_score']} < {MIN_CONCLUSION_SCORE}."
        )
        return 1

    if result["source_score"] < MIN_SOURCE_SCORE:
        print(
            "Single quiz regression failed: "
            f"source score {result['source_score']} < {MIN_SOURCE_SCORE}."
        )
        return 1

    if result["confidence_score"] < MIN_CONFIDENCE_SCORE:
        print(
            "Single quiz regression failed: "
            f"confidence score {result['confidence_score']} < {MIN_CONFIDENCE_SCORE}."
        )
        return 1

    if result["final_score"] < MIN_FINAL_SCORE:
        print(
            "Single quiz regression failed: "
            f"final score {result['final_score']:.2f} < {MIN_FINAL_SCORE}."
        )
        return 1

    if result["time_rating"] == FAIL_TIME_RATING:
        print("Single quiz regression failed: time rating is 不及格.")
        return 1

    print("Single quiz regression passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
