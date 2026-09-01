from email_assistant.main import _analysis_log_record
from email_assistant.models import EmailAnalysis, EmailCategory, Importance


def test_analysis_log_record_omits_evidence_and_body_details():
    record = _analysis_log_record(
        EmailAnalysis(
            email_id="1",
            subject="Course registration",
            category=EmailCategory.MUST_ACTION,
            importance=Importance.HIGH,
            summary="需要确认 course registration。",
            mandatory=True,
            action_required=True,
            action="确认 course registration。",
            deadline="2026-09-02",
            event_time=None,
            location=None,
            evidence="You are required to confirm",
            confidence=0.96,
        )
    )

    assert "summary" not in record
    assert "action" not in record
    assert "deadline" not in record
    assert "evidence" not in record
    assert record["has_deadline"] is True
