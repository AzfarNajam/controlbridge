"""A deliberately narrow, deterministic storage configuration assessment."""

from datetime import datetime, timedelta, timezone

CONTROL_ID = "CB-STORAGE-001"
RULE_VERSION = "1.0"
MAX_AGE_HOURS = 24


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be an ISO 8601 string with timezone")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate(document):
    if not isinstance(document, dict) or document.get("schema_version") != "1.0":
        raise ValueError("Expected schema_version 1.0")
    if document.get("mode") != "fixture":
        raise ValueError("Only explicitly labelled fixture input is supported")
    if not isinstance(document.get("evidence"), list) or not document["evidence"]:
        raise ValueError("Evidence must be a non-empty list; empty inventory is not a pass")
    ids = set()
    for item in document["evidence"]:
        if not isinstance(item, dict):
            raise ValueError("Each evidence record must be an object")
        for key in ("id", "resource_id", "subscription_id", "source", "collector_version"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"Evidence requires non-empty {key}")
        if item["id"] in ids:
            raise ValueError(f"Duplicate evidence ID: {item['id']}")
        ids.add(item["id"])
        timestamp(item.get("collected_at"))
        if item.get("collection_status") not in ("success", "error"):
            raise ValueError("collection_status must be success or error")
        if not isinstance(item.get("properties"), dict):
            raise ValueError("properties must be an object")
        value = item["properties"].get("allowBlobPublicAccess")
        if value is not None and type(value) is not bool:
            raise ValueError("allowBlobPublicAccess must be boolean or null, never a string")
    return document


def assess(item, as_of):
    """Evaluate evidence quality before evaluating the observed configuration."""
    age = as_of - timestamp(item["collected_at"])
    result, reason = "unknown", ""
    if item["collection_status"] != "success":
        reason = "Collection failed; the resource setting has not been established."
    elif age < timedelta(0):
        reason = "Evidence timestamp is in the future relative to assessment time."
    elif age > timedelta(hours=MAX_AGE_HOURS):
        reason = "Evidence exceeds the local lab freshness policy of 24 hours."
    else:
        value = item["properties"].get("allowBlobPublicAccess")
        if value is False:
            result = "pass"
            reason = "Account-level anonymous blob access is explicitly disallowed."
        elif value is True:
            result = "fail"
            reason = "Account allows anonymous blob access configuration. Actual exposure depends on container settings; it is not established here."
        else:
            reason = "Explicit account setting is missing or null; no default is inferred."
    return {
        "control_id": CONTROL_ID, "rule_version": RULE_VERSION,
        "evidence_id": item["id"], "resource_id": item["resource_id"],
        "result": result, "reason": reason,
    }
