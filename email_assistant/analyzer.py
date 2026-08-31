from __future__ import annotations

import json
import re
from typing import Protocol

from email_assistant.models import EmailAnalysis, EmailCategory, Importance, LLMImage, ParsedEmail


class LLMProvider(Protocol):
    def analyze(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        images: list[LLMImage] | None = None,
    ) -> str:
        ...


SYSTEM_PROMPT = """You classify university student emails for actionability.

Return only valid JSON with exactly these fields:
category, importance, summary, mandatory, action_required, action, deadline,
event_time, location, evidence, confidence.

category must be one of:
MUST_ACTION, MUST_ATTEND, ACADEMIC_NOTICE, OPTIONAL_EVENT, GENERAL.

importance must be one of: HIGH, MEDIUM, LOW.

Rules:
- Write summary and action in Simplified Chinese with natural English terms mixed in where
  Hong Kong/mainland students would normally use them.
- Do not translate common academic/campus terms when English is more natural, such as seminar,
  add/drop, registration, orientation, deadline, venue, workshop, RPg, MSc, credit, timetable,
  handbook, notice, application, showcase, career talk, and office hour.
- Keep category and importance as the required English enum values.
- Keep deadline and event_time in unambiguous ISO-like date/time text when possible.
- Keep evidence as a short exact phrase from the email when possible; if the evidence is
  visual-only, summarize the visual evidence in Simplified Chinese with natural English terms.
- "You are invited to attend" means OPTIONAL_EVENT unless mandatory wording is present.
- Use MUST_ATTEND only when attendance is explicitly compulsory, required, mandatory, or equivalent.
- Use MUST_ACTION when the student must submit, register, confirm, pay, complete, upload, reply, or perform another required task.
- Use ACADEMIC_NOTICE for important academic information without a required action.
- If images are provided, inspect them for deadlines, event times, locations, QR poster text,
  mandatory wording, and action instructions that may not appear in the plain text body.
- If a field is unknown, use null.
- confidence must be a number between 0 and 1.
"""


class EmailAnalyzer:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def analyze(self, parsed: ParsedEmail, *, images: list[LLMImage] | None = None) -> EmailAnalysis:
        content = self._llm.analyze(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=_build_user_prompt(parsed, images=images or []),
            images=images or [],
        )
        payload = _extract_json_object(content)
        return _analysis_from_payload(parsed.raw.id, payload)


def _build_user_prompt(parsed: ParsedEmail, *, images: list[LLMImage]) -> str:
    raw = parsed.raw
    image_summary = "\n".join(
        f"- source={image.source}, attachment_id={image.attachment_id or 'none'}, "
        f"filename={image.filename or 'unknown'}, content_type={image.content_type or 'unknown'}, "
        f"size={image.size or 'unknown'}, sha256={image.sha256 or 'not_stored'}"
        for image in images
    )
    if not image_summary:
        image_summary = "No images provided."

    return f"""Subject: {raw.subject}
From: {raw.sender}
To: {", ".join(raw.to)}
Received for: {", ".join(raw.received_for)}
Created at: {raw.created_at.isoformat() if raw.created_at else "unknown"}

Images:
{image_summary}

Email body:
{parsed.clean_text}
"""


def _extract_json_object(content: str) -> dict[str, object]:
    try:
        decoded = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise ValueError(f"LLM did not return JSON: {content[:300]}")
        decoded = json.loads(match.group(0))

    if not isinstance(decoded, dict):
        raise ValueError("LLM response JSON must be an object.")
    return decoded


def _analysis_from_payload(email_id: str, payload: dict[str, object]) -> EmailAnalysis:
    category = _enum_value(EmailCategory, payload.get("category"), EmailCategory.GENERAL)
    importance = _enum_value(Importance, payload.get("importance"), Importance.LOW)
    confidence = _float_between(payload.get("confidence"), minimum=0.0, maximum=1.0)

    mandatory = bool(payload.get("mandatory", category == EmailCategory.MUST_ATTEND))
    action_required = bool(
        payload.get("action_required", category in {EmailCategory.MUST_ACTION, EmailCategory.MUST_ATTEND})
    )

    return EmailAnalysis(
        email_id=email_id,
        category=category,
        importance=importance,
        summary=_optional_str(payload.get("summary")) or "",
        mandatory=mandatory,
        action_required=action_required,
        action=_optional_str(payload.get("action")),
        deadline=_optional_str(payload.get("deadline")),
        event_time=_optional_str(payload.get("event_time")),
        location=_optional_str(payload.get("location")),
        evidence=_optional_str(payload.get("evidence")),
        confidence=confidence,
    )


def _enum_value(enum_type, value: object, default):
    if isinstance(value, str):
        try:
            return enum_type(value.strip().upper())
        except ValueError:
            return default
    return default


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    return text


def _float_between(value: object, *, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return minimum
    return min(max(parsed, minimum), maximum)
