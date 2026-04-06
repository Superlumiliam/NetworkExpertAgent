import json
import re
from typing import Any


STRUCTURED_ANSWER_KEYS = ("结论", "出处定位", "协议原文节选")

_SMART_QUOTES_TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
)

_FIELD_ALIASES = {
    "结论": ("结论", "conclusion", "answer", "final_answer"),
    "出处定位": ("出处定位", "出处", "source", "citation", "location"),
    "协议原文节选": (
        "协议原文节选",
        "协议原文",
        "原文节选",
        "quote",
        "quoted_text",
        "excerpt",
        "ref",
    ),
}

_LABEL_TO_KEY = {
    alias.lower(): key
    for key, aliases in _FIELD_ALIASES.items()
    for alias in aliases
}

_LINE_FIELD_RE = re.compile(
    r"^\s*(结论|出处定位|协议原文节选|conclusion|source|quote|excerpt|ref)\s*[:：]\s*(.*)$",
    re.IGNORECASE,
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_json_text(raw_text: str) -> str:
    return raw_text.translate(_SMART_QUOTES_TRANSLATION).strip()


def _extract_json_candidate(raw_text: str) -> dict[str, Any] | None:
    normalized = _normalize_json_text(raw_text)
    candidates = []

    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", normalized, re.DOTALL)
    if fenced_match:
        candidates.append(fenced_match.group(1))

    if normalized.startswith("{") and normalized.endswith("}"):
        candidates.append(normalized)

    first_brace = normalized.find("{")
    last_brace = normalized.rfind("}")
    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        candidates.append(normalized[first_brace:last_brace + 1])

    for candidate in candidates:
        candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    return None


def _extract_line_based_fields(raw_text: str) -> dict[str, str]:
    values = {key: "" for key in STRUCTURED_ANSWER_KEYS}
    current_key: str | None = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _LINE_FIELD_RE.match(line)
        if match:
            label = match.group(1).lower()
            current_key = _LABEL_TO_KEY.get(label)
            if current_key:
                values[current_key] = match.group(2).strip()
            continue

        if current_key:
            existing = values[current_key]
            values[current_key] = f"{existing} {line}".strip()

    return values


def normalize_structured_answer(
    payload: Any,
    *,
    default_conclusion: str = "",
    default_source: str = "未找到明确出处",
    default_quote: str = "未找到可核对的协议原文节选。",
) -> dict[str, str]:
    values = {key: "" for key in STRUCTURED_ANSWER_KEYS}

    if isinstance(payload, dict):
        candidate = payload
    else:
        raw_text = _normalize_text(payload)
        candidate = _extract_json_candidate(raw_text)
        if candidate is None:
            values.update(_extract_line_based_fields(raw_text))
            if not any(values.values()):
                values["结论"] = raw_text
        else:
            payload = candidate

    if isinstance(payload, dict):
        for canonical_key, aliases in _FIELD_ALIASES.items():
            for alias in aliases:
                if alias in payload and _normalize_text(payload[alias]):
                    values[canonical_key] = _normalize_text(payload[alias])
                    break

    values["结论"] = values["结论"] or default_conclusion
    values["出处定位"] = values["出处定位"] or default_source
    values["协议原文节选"] = values["协议原文节选"] or default_quote
    return values


def build_structured_answer(
    conclusion: str,
    source: str,
    quote: str,
) -> str:
    payload = {
        "结论": _normalize_text(conclusion),
        "出处定位": _normalize_text(source),
        "协议原文节选": _normalize_text(quote),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def coerce_structured_answer(
    payload: Any,
    *,
    default_conclusion: str = "",
    default_source: str = "未找到明确出处",
    default_quote: str = "未找到可核对的协议原文节选。",
) -> str:
    normalized = normalize_structured_answer(
        payload,
        default_conclusion=default_conclusion,
        default_source=default_source,
        default_quote=default_quote,
    )
    return build_structured_answer(
        normalized["结论"],
        normalized["出处定位"],
        normalized["协议原文节选"],
    )
