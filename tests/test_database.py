from datetime import datetime, timezone

from email_assistant.database import EmailDatabase
from email_assistant.models import EmailAnalysis, EmailCategory, Importance, RawEmail


def test_database_saves_and_deduplicates_analysis(tmp_path):
    db_path = tmp_path / "emails.db"
    email = RawEmail(
        id="email-1",
        subject="Orientation",
        sender="school@example.com",
        to=["polyu@faloukulee.resend.app"],
        created_at=datetime.now(timezone.utc),
    )
    analysis = EmailAnalysis(
        email_id="email-1",
        category=EmailCategory.MUST_ATTEND,
        importance=Importance.HIGH,
        summary="Orientation is compulsory.",
        mandatory=True,
        action_required=True,
        action="Attend orientation",
        deadline=None,
        event_time="2026-09-03 14:30",
        location="QR611",
        evidence="Attendance is compulsory.",
        confidence=0.97,
    )

    with EmailDatabase(f"sqlite:///{db_path}") as db:
        db.initialize()
        assert db.is_processed("email-1") is False
        db.save_email_analysis(email=email, clean_text="Attendance is compulsory.", analysis=analysis)

        assert db.is_processed("email-1") is True
        assert db.list_recent_analyses()[0].category == EmailCategory.MUST_ATTEND
