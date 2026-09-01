from email_assistant.analyzer import EmailAnalyzer
from email_assistant.models import EmailCategory, ParsedEmail, RawEmail


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content

    def analyze(self, *, system_prompt: str, user_prompt: str, images=None) -> str:
        return self.content


def test_analyzer_parses_json_and_normalizes_category():
    llm = FakeLLM(
        """
        {
          "category": "OPTIONAL_EVENT",
          "importance": "MEDIUM",
          "summary": "AI career seminar invitation.",
          "mandatory": false,
          "action_required": false,
          "action": null,
          "deadline": null,
          "event_time": "2026-09-03 14:30",
          "location": "QR611",
          "evidence": "You are invited to attend",
          "confidence": 0.91
        }
        """
    )
    parsed = ParsedEmail(
        raw=RawEmail(
            id="email-1",
            subject="Seminar",
            sender="school@example.com",
            to=["polyu@faloukulee.resend.app"],
            created_at=None,
        ),
        clean_text="You are invited to attend.",
    )

    analysis = EmailAnalyzer(llm).analyze(parsed)

    assert analysis.category == EmailCategory.OPTIONAL_EVENT
    assert analysis.mandatory is False
    assert analysis.confidence == 0.91


def test_analyzer_downgrades_departmental_seminar_credit_requirement():
    llm = FakeLLM(
        """
        {
          "category": "MUST_ACTION",
          "importance": "HIGH",
          "summary": "所有 RPg 学生必须从 departmental seminar subjects 修读至少 1 个 credit。",
          "mandatory": true,
          "action_required": true,
          "action": "确认自己会从 departmental seminar subjects 获得至少 1 个 credit。",
          "deadline": "2026-09-07",
          "event_time": null,
          "location": null,
          "evidence": "All RPg students must earn at least 1 credit from departmental seminar subjects",
          "confidence": 0.94
        }
        """
    )
    parsed = ParsedEmail(
        raw=RawEmail(
            id="email-2",
            subject="GS Flash",
            sender="school@example.com",
            to=["polyu@faloukulee.resend.app"],
            created_at=None,
        ),
        clean_text="All RPg students must earn at least 1 credit from departmental seminar subjects.",
    )

    analysis = EmailAnalyzer(llm).analyze(parsed)

    assert analysis.category == EmailCategory.ACADEMIC_NOTICE
    assert analysis.mandatory is False
    assert analysis.action_required is False
    assert analysis.action is None
    assert analysis.deadline is None
    assert analysis.evidence is None
    assert "departmental seminar" not in analysis.summary
    assert "credit" not in analysis.summary
