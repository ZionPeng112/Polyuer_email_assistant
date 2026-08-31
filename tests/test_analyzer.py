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
