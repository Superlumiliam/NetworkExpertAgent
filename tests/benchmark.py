import asyncio
import difflib
import json
import os
import re
import sys
import time
from typing import Any, Dict, List

# Add project root to path
sys.path.append(os.getcwd())

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

import src.config.settings as cfg
from src.core.answer_format import normalize_structured_answer
from src.main import process_question
from tests.benchmark_metrics import (
    CONCLUSION_WEIGHT,
    CONFIDENCE_WEIGHT,
    SOURCE_WEIGHT,
    TIME_WEIGHT,
    combine_weighted_score,
    evaluate_time,
)


QUIZ_PATH = "tests/quiz.md"

_SMART_QUOTES_TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
)

_RFC_ID_RE = re.compile(r"rfc\s*[- ]?\s*(\d+)", re.IGNORECASE)
_SECTION_RE = re.compile(r"(?:section|sec\.?|§)\s*([A-Za-z]?\d+(?:\.\d+)*)", re.IGNORECASE)
_CHINESE_SECTION_RE = re.compile(r"([A-Za-z]?\d+(?:\.\d+)*)\s*节", re.IGNORECASE)
_APPENDIX_RE = re.compile(r"(?:appendix|附录)\s*([A-Za-z](?:\.\d+)*)", re.IGNORECASE)


def _load_quiz_payload(file_path: str) -> dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read().strip()

    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
    json_text = fenced_match.group(1) if fenced_match else content
    normalized_json_text = json_text.translate(_SMART_QUOTES_TRANSLATION)
    normalized_json_text = re.sub(r",(\s*[}\]])", r"\1", normalized_json_text)
    return json.loads(normalized_json_text)


def parse_quiz(file_path: str) -> List[Dict[str, Any]]:
    """Parse the quiz markdown file containing JSON content."""
    payload = _load_quiz_payload(file_path)
    questions = []

    for item in payload.get("questions", []):
        question = str(item.get("quiz", "")).strip()
        expected_answer = normalize_structured_answer(
            item.get("expected_answer", {}),
            default_conclusion="",
            default_source="",
            default_quote="",
        )
        if not question:
            continue

        questions.append(
            {
                "index": item.get("index", len(questions) + 1),
                "question": question,
                "expected": expected_answer,
            }
        )

    return questions


def _normalize_for_compare(value: str) -> str:
    normalized = value.translate(_SMART_QUOTES_TRANSLATION).casefold()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip(" \"'")


def _extract_source_locator(source: str) -> tuple[str | None, str | None]:
    rfc_match = _RFC_ID_RE.search(source)
    appendix_match = _APPENDIX_RE.search(source)
    section_match = _SECTION_RE.search(source) or _CHINESE_SECTION_RE.search(source)

    rfc_id = None
    locator = None

    if rfc_match:
        rfc_id = str(int(rfc_match.group(1)))

    if appendix_match:
        locator = f"appendix:{appendix_match.group(1).upper()}"
    elif section_match:
        locator = f"section:{section_match.group(1).upper()}"

    return rfc_id, locator


def evaluate_source_accuracy(expected_source: str, actual_source: str) -> int:
    """Score whether RFC number and section location are correctly cited."""
    expected_normalized = _normalize_for_compare(expected_source)
    actual_normalized = _normalize_for_compare(actual_source)

    if not actual_normalized:
        return 0

    if expected_normalized and expected_normalized == actual_normalized:
        return 10

    expected_rfc_id, expected_locator = _extract_source_locator(expected_source)
    actual_rfc_id, actual_locator = _extract_source_locator(actual_source)

    score = 0
    if expected_rfc_id and actual_rfc_id and expected_rfc_id == actual_rfc_id:
        score += 5

    if expected_locator and actual_locator and expected_locator == actual_locator:
        score += 5
    elif expected_locator and actual_locator:
        expected_core = expected_locator.split(":", 1)[1]
        actual_core = actual_locator.split(":", 1)[1]
        if expected_core.split(".")[0] == actual_core.split(".")[0]:
            score += 3

    if score == 0:
        similarity = difflib.SequenceMatcher(
            None,
            expected_normalized,
            actual_normalized,
        ).ratio()
        if similarity >= 0.9:
            return 9
        if similarity >= 0.75:
            return 7
        if similarity >= 0.6:
            return 5
        if similarity >= 0.4:
            return 3
        return 0

    return min(score, 10)


def evaluate_confidence(expected_quote: str, actual_quote: str, source_score: int) -> int:
    """
    Score how closely the quoted protocol excerpt matches the real RFC text proxy.

    The expected quote in quiz.md is treated as the canonical RFC excerpt.
    """
    expected_normalized = _normalize_for_compare(expected_quote)
    actual_normalized = _normalize_for_compare(actual_quote)

    if not actual_normalized:
        return 0

    if expected_normalized and (
        expected_normalized in actual_normalized or actual_normalized in expected_normalized
    ):
        score = 10
    else:
        similarity = difflib.SequenceMatcher(
            None,
            expected_normalized,
            actual_normalized,
        ).ratio()
        if similarity >= 0.92:
            score = 9
        elif similarity >= 0.8:
            score = 8
        elif similarity >= 0.65:
            score = 6
        elif similarity >= 0.5:
            score = 4
        elif similarity >= 0.35:
            score = 2
        else:
            score = 0

    if source_score < 5:
        score = min(score, 4)

    return score


async def evaluate_conclusion(question: str, expected: str, actual: str) -> int:
    """
    Evaluate the conclusion field using an LLM judge.
    Returns a score from 0 to 10.
    """
    if not actual.strip():
        return 0

    llm = ChatOpenAI(
        base_url=cfg.OPENROUTER_BASE_URL,
        api_key=cfg.OPENROUTER_API_KEY,
        model=cfg.DEFAULT_MODEL,
        temperature=0,
    )

    system = """You are an impartial judge.
Evaluate only the correctness of the actual conclusion against the expected conclusion for the given networking question.

Ignore formatting, citation, and quoted RFC text.
Assign an integer score from 0 to 10:
- 10: Correct conclusion with no meaningful factual error
- 8: Essentially correct with minor wording differences
- 5: Partially correct or incomplete
- 0: Incorrect, contradictory, or irrelevant

Return ONLY the integer score.
"""

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            (
                "human",
                "Question: {question}\nExpected Conclusion: {expected}\nActual Conclusion: {actual}",
            ),
        ]
    )

    chain = prompt | llm | StrOutputParser()

    try:
        score_str = await chain.ainvoke(
            {
                "question": question,
                "expected": expected,
                "actual": actual,
            }
        )
        match = re.search(r"\d+", score_str)
        return int(match.group()) if match else 0
    except Exception as exc:
        print(f"Conclusion evaluation error: {exc}")
        return 0


async def run_single_question(
    question: str,
    expected: Dict[str, str],
    question_number: int = 1,
) -> Dict[str, Any]:
    """Run the full benchmark flow for a single question."""
    print(f"\nProcessing Q{question_number}: {question}")

    start_time = time.time()
    try:
        actual = await process_question(question)
    except Exception as exc:
        actual = f"Error: {exc}"
    end_time = time.time()

    duration = end_time - start_time
    actual_structured = normalize_structured_answer(
        actual,
        default_conclusion=actual,
    )

    conclusion_score = await evaluate_conclusion(
        question,
        expected["结论"],
        actual_structured["结论"],
    )
    source_score = evaluate_source_accuracy(
        expected["出处定位"],
        actual_structured["出处定位"],
    )
    confidence_score = evaluate_confidence(
        expected["协议原文节选"],
        actual_structured["协议原文节选"],
        source_score,
    )
    time_evaluation = evaluate_time(duration)
    final_score = combine_weighted_score(
        conclusion_score,
        source_score,
        confidence_score,
        time_evaluation.score,
    )

    print(
        f"Time: {duration:.2f}s | "
        f"Conclusion: {conclusion_score}/10 | "
        f"Source: {source_score}/10 | "
        f"Confidence: {confidence_score}/10 | "
        f"Time Grade: {time_evaluation.label} ({time_evaluation.score}/10) | "
        f"Final: {final_score:.2f}/10"
    )
    print(
        "Time Thresholds: "
        f"excellent <= {time_evaluation.excellent_threshold:.2f}s, "
        f"good <= {time_evaluation.good_threshold:.2f}s, "
        f"pass <= {time_evaluation.pass_threshold:.2f}s"
    )
    print(f"Actual Answer: {actual[:200]}...")

    return {
        "question": question,
        "expected": expected,
        "actual": actual,
        "actual_structured": actual_structured,
        "conclusion_score": conclusion_score,
        "source_score": source_score,
        "confidence_score": confidence_score,
        "time_score": time_evaluation.score,
        "time_rating": time_evaluation.rating,
        "time_rating_label": time_evaluation.label,
        "final_score": final_score,
        "time": duration,
    }


async def run_benchmark():
    """Run the benchmark with structured answer scoring and fixed-threshold time scoring."""
    print("Starting Benchmark...")
    questions = parse_quiz(QUIZ_PATH)
    print("Fixed Time Thresholds: 0-30s=优秀, 30-60s=良好, 60-120s=及格, >120s=不及格")

    total_conclusion_score = 0
    total_source_score = 0
    total_confidence_score = 0
    total_time_score = 0
    total_final_score = 0
    total_time = 0
    rating_counts = {
        "excellent": 0,
        "good": 0,
        "pass": 0,
        "fail": 0,
    }
    results = []

    for i, item in enumerate(questions):
        result = await run_single_question(
            item["question"],
            item["expected"],
            question_number=i + 1,
        )

        total_time += result["time"]
        total_conclusion_score += result["conclusion_score"]
        total_source_score += result["source_score"]
        total_confidence_score += result["confidence_score"]
        total_time_score += result["time_score"]
        total_final_score += result["final_score"]
        rating_counts[result["time_rating"]] += 1

        results.append(
            {
                "question": result["question"],
                "conclusion_score": result["conclusion_score"],
                "source_score": result["source_score"],
                "confidence_score": result["confidence_score"],
                "time_score": result["time_score"],
                "time_rating": result["time_rating_label"],
                "final_score": result["final_score"],
                "time": result["time"],
            }
        )

    avg_conclusion_score = total_conclusion_score / len(questions) if questions else 0
    avg_source_score = total_source_score / len(questions) if questions else 0
    avg_confidence_score = total_confidence_score / len(questions) if questions else 0
    avg_time_score = total_time_score / len(questions) if questions else 0
    avg_final_score = total_final_score / len(questions) if questions else 0
    avg_time = total_time / len(questions) if questions else 0

    print("\n" + "=" * 50)
    print("Benchmark Complete")
    print(
        "Weighted Score Rule: "
        f"conclusion {CONCLUSION_WEIGHT:.0%} + "
        f"source {SOURCE_WEIGHT:.0%} + "
        f"confidence {CONFIDENCE_WEIGHT:.0%} + "
        f"time {TIME_WEIGHT:.0%}"
    )
    print(f"Average Conclusion Score: {avg_conclusion_score:.2f}/10")
    print(f"Average Source Score: {avg_source_score:.2f}/10")
    print(f"Average Confidence Score: {avg_confidence_score:.2f}/10")
    print(f"Average Time Score: {avg_time_score:.2f}/10")
    print(f"Average Final Score: {avg_final_score:.2f}/10")
    print(f"Average Time: {avg_time:.2f}s")
    print(
        "Time Rating Counts: "
        f"优秀={rating_counts['excellent']}, "
        f"良好={rating_counts['good']}, "
        f"及格={rating_counts['pass']}, "
        f"不及格={rating_counts['fail']}"
    )
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
