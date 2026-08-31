from email_assistant.digest import build_daily_digest
from email_assistant.digest import build_daily_digest_zh
from email_assistant.models import EmailAnalysis, EmailCategory, Importance


def test_digest_groups_by_category_order():
    digest = build_daily_digest(
        [
            EmailAnalysis(
                email_id="1",
                category=EmailCategory.OPTIONAL_EVENT,
                importance=Importance.LOW,
                summary="Library Workshop",
                mandatory=False,
                action_required=False,
                action=None,
                deadline=None,
                event_time=None,
                location=None,
                evidence=None,
                confidence=0.8,
            ),
            EmailAnalysis(
                email_id="2",
                category=EmailCategory.MUST_ACTION,
                importance=Importance.HIGH,
                summary="Course registration confirmation",
                mandatory=True,
                action_required=True,
                action="Confirm registration",
                deadline="2026-09-02",
                event_time=None,
                location=None,
                evidence="You are required to confirm",
                confidence=0.96,
            ),
        ]
    )

    assert digest.index("Must Do") < digest.index("Optional Events")
    assert "Deadline: 2026-09-02" in digest


def test_zh_digest_always_includes_optional_and_empty_sections():
    digest = build_daily_digest_zh([])

    assert "过去 24 小时共分析 0 封邮件" in digest
    assert "必须处理 (0)" not in digest
    assert "可以考虑参加 / 可做 (0)" not in digest


def test_zh_digest_keeps_cleaned_email_title():
    digest = build_daily_digest_zh(
        [
            EmailAnalysis(
                email_id="1",
                subject="转发: Seminar Notice",
                category=EmailCategory.OPTIONAL_EVENT,
                importance=Importance.MEDIUM,
                summary="这个 seminar 可以按兴趣参加。",
                mandatory=False,
                action_required=False,
                action="有兴趣可 register。",
                deadline=None,
                event_time=None,
                location=None,
                evidence="You are invited",
                confidence=0.9,
            )
        ]
    )

    assert "Seminar Notice" in digest
    assert "转发:" not in digest
