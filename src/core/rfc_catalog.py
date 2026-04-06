import json
import re
from pathlib import Path
from typing import Any, Optional


PROTOCOL_SPECS_PATH = Path(__file__).with_name("protocol_specs.json")


def normalize_rfc_id(value: str) -> str:
    return str(value).lower().replace("rfc", "").strip()


def _load_protocol_specs_payload() -> dict[str, Any]:
    with PROTOCOL_SPECS_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise RuntimeError("protocol_specs.json must contain a top-level JSON object.")

    return payload


def load_protocol_specs() -> list[dict[str, Any]]:
    payload = _load_protocol_specs_payload()
    raw_protocols = payload.get("protocols")

    if not isinstance(raw_protocols, list) or not raw_protocols:
        raise RuntimeError("protocol_specs.json must define a non-empty 'protocols' array.")

    normalized_protocols: list[dict[str, Any]] = []
    for raw_protocol in raw_protocols:
        if not isinstance(raw_protocol, dict):
            raise RuntimeError("Each protocol spec must be a JSON object.")

        display_name = str(raw_protocol["display_name"]).strip()
        latest_rfc_id = normalize_rfc_id(raw_protocol["latest_rfc_id"])

        raw_rfc_ids = raw_protocol.get("rfc_ids", [latest_rfc_id])
        if not isinstance(raw_rfc_ids, list) or not raw_rfc_ids:
            raise RuntimeError(f"Protocol '{display_name}' must define a non-empty 'rfc_ids' array.")

        rfc_ids = []
        for rfc_id in raw_rfc_ids:
            normalized_rfc = normalize_rfc_id(rfc_id)
            if normalized_rfc not in rfc_ids:
                rfc_ids.append(normalized_rfc)
        if latest_rfc_id not in rfc_ids:
            rfc_ids.insert(0, latest_rfc_id)

        supported_aliases = _normalize_alias_list(raw_protocol.get("supported_aliases", []))
        unsupported_aliases = _normalize_alias_list(raw_protocol.get("unsupported_aliases", []))
        if not supported_aliases:
            raise RuntimeError(
                f"Protocol '{display_name}' must define a non-empty 'supported_aliases' array."
            )

        normalized_protocols.append(
            {
                "key": str(raw_protocol.get("key", display_name)).strip().lower(),
                "display_name": display_name,
                "latest_rfc_id": latest_rfc_id,
                "rfc_ids": tuple(rfc_ids),
                "supported_aliases": supported_aliases,
                "unsupported_aliases": unsupported_aliases,
            }
        )

    return normalized_protocols


def _normalize_alias_list(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        raise RuntimeError("Protocol aliases must be provided as JSON arrays.")

    normalized_values: list[str] = []
    for value in values:
        normalized_value = str(value).strip().lower()
        if normalized_value and normalized_value not in normalized_values:
            normalized_values.append(normalized_value)

    return tuple(normalized_values)


def _compile_alias_pattern(alias: str) -> re.Pattern[str]:
    tokens = [token for token in re.split(r"[\s-]+", alias) if token]
    pattern = r"[\s-]*".join(re.escape(token) for token in tokens)
    return re.compile(rf"(?<![A-Za-z0-9])(?:{pattern})(?![A-Za-z0-9])", re.IGNORECASE)


def _question_matches_alias(question: str, alias: str) -> bool:
    return _compile_alias_pattern(alias).search(question) is not None


def get_supported_rfc_ids() -> tuple[str, ...]:
    ordered_rfc_ids: list[str] = []
    for protocol in load_protocol_specs():
        for rfc_id in protocol["rfc_ids"]:
            if rfc_id not in ordered_rfc_ids:
                ordered_rfc_ids.append(rfc_id)
    return tuple(ordered_rfc_ids)


def get_supported_protocol_tags() -> tuple[str, ...]:
    return tuple(protocol["display_name"] for protocol in load_protocol_specs())


def get_not_ingested_message() -> str:
    supported_protocols = "、".join(get_supported_protocol_tags())
    return (
        f"当前仅支持已预热的 {supported_protocols} 最新版协议内容，"
        "所问协议版本或 RFC 暂未入库，系统不会在线补库。"
    )


def get_protocol_for_rfc(rfc_id: str) -> Optional[str]:
    normalized_rfc_id = normalize_rfc_id(rfc_id)
    for protocol in load_protocol_specs():
        if normalized_rfc_id in protocol["rfc_ids"]:
            return protocol["display_name"]
    return None


def resolve_question_scope(question: str) -> dict[str, object]:
    not_ingested_message = get_not_ingested_message()
    protocols = load_protocol_specs()
    supported_rfc_ids = {
        rfc_id
        for protocol in protocols
        for rfc_id in protocol["rfc_ids"]
    }

    explicit_rfc_ids = [
        normalize_rfc_id(match)
        for match in re.findall(r"\brfc[\s-]*(\d{3,5})\b", question, flags=re.IGNORECASE)
    ]
    explicit_rfc_ids = list(dict.fromkeys(explicit_rfc_ids))

    if explicit_rfc_ids:
        unsupported_ids = [rfc_id for rfc_id in explicit_rfc_ids if rfc_id not in supported_rfc_ids]
        if unsupported_ids:
            return {
                "target_rfc_ids": [],
                "availability_status": "not_ingested",
                "availability_message": not_ingested_message,
            }

        return {
            "target_rfc_ids": explicit_rfc_ids,
            "availability_status": "supported",
            "availability_message": "",
        }

    for protocol in protocols:
        if any(
            _question_matches_alias(question, alias)
            for alias in protocol["unsupported_aliases"]
        ):
            return {
                "target_rfc_ids": [],
                "availability_status": "not_ingested",
                "availability_message": not_ingested_message,
            }

    for protocol in protocols:
        if any(
            _question_matches_alias(question, alias)
            for alias in protocol["supported_aliases"]
        ):
            return {
                "target_rfc_ids": [protocol["latest_rfc_id"]],
                "availability_status": "supported",
                "availability_message": "",
            }

    return {
        "target_rfc_ids": [],
        "availability_status": "not_ingested",
        "availability_message": not_ingested_message,
    }
