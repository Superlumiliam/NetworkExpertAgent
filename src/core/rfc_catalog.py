import re
from typing import Optional


SUPPORTED_RFC_IDS = ("3376", "3810", "7761")
SUPPORTED_PROTOCOL_TAGS = ("IGMP", "MLD", "PIM")
NOT_INGESTED_MESSAGE = (
    "当前仅支持已预热的 IGMP、MLD、PIM 最新版协议内容，"
    "所问协议版本或 RFC 暂未入库，系统不会在线补库。"
)

_RFC_TO_PROTOCOL = {
    "3376": "IGMP",
    "3810": "MLD",
    "7761": "PIM",
}

def _compile_protocol_pattern(pattern: str) -> re.Pattern[str]:
    """Match protocol tokens even when they are adjacent to CJK text like `PIM协议`."""
    return re.compile(rf"(?<![A-Za-z0-9])(?:{pattern})(?![A-Za-z0-9])", re.IGNORECASE)


_SUPPORTED_PROTOCOL_PATTERNS = (
    (_compile_protocol_pattern(r"pim(?:[\s-]*sm)?"), ["7761"]),
    (_compile_protocol_pattern(r"mldv?2"), ["3810"]),
    (_compile_protocol_pattern(r"mld"), ["3810"]),
    (_compile_protocol_pattern(r"igmpv?3"), ["3376"]),
    (_compile_protocol_pattern(r"igmp"), ["3376"]),
)

_UNSUPPORTED_VERSION_PATTERNS = (
    _compile_protocol_pattern(r"igmpv?2"),
    _compile_protocol_pattern(r"mldv?1"),
)


def normalize_rfc_id(value: str) -> str:
    return str(value).lower().replace("rfc", "").strip()


def get_protocol_for_rfc(rfc_id: str) -> Optional[str]:
    return _RFC_TO_PROTOCOL.get(normalize_rfc_id(rfc_id))


def resolve_question_scope(question: str) -> dict[str, object]:
    explicit_rfc_ids = [
        normalize_rfc_id(match)
        for match in re.findall(r"\brfc[\s-]*(\d{3,5})\b", question, flags=re.IGNORECASE)
    ]
    explicit_rfc_ids = list(dict.fromkeys(explicit_rfc_ids))

    if explicit_rfc_ids:
        unsupported_ids = [rfc_id for rfc_id in explicit_rfc_ids if rfc_id not in SUPPORTED_RFC_IDS]
        if unsupported_ids:
            return {
                "target_rfc_ids": [],
                "availability_status": "not_ingested",
                "availability_message": NOT_INGESTED_MESSAGE,
            }

        return {
            "target_rfc_ids": explicit_rfc_ids,
            "availability_status": "supported",
            "availability_message": "",
        }

    for pattern in _UNSUPPORTED_VERSION_PATTERNS:
        if pattern.search(question):
            return {
                "target_rfc_ids": [],
                "availability_status": "not_ingested",
                "availability_message": NOT_INGESTED_MESSAGE,
            }

    for pattern, target_rfc_ids in _SUPPORTED_PROTOCOL_PATTERNS:
        if pattern.search(question):
            return {
                "target_rfc_ids": target_rfc_ids,
                "availability_status": "supported",
                "availability_message": "",
            }

    return {
        "target_rfc_ids": [],
        "availability_status": "not_ingested",
        "availability_message": NOT_INGESTED_MESSAGE,
    }
