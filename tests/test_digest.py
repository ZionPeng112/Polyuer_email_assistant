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


def test_zh_digest_suppresses_departmental_seminar_credit_must_item():
    digest = build_daily_digest_zh(
        [
            EmailAnalysis(
                email_id="1",
                subject="GS Flash | Aug 2026",
                category=EmailCategory.MUST_ACTION,
                importance=Importance.HIGH,
                summary="GS Flash 提醒所有 RPg 学生必须从 departmental seminar subjects 修读至少 1 个 credit。",
                mandatory=True,
                action_required=True,
                action="确认自己会从 departmental seminar subjects 获得至少 1 个 credit。",
                deadline="2026-09-07",
                event_time=None,
                location=None,
                evidence="All RPg students must earn at least 1 credit from departmental seminar subjects",
                confidence=0.94,
            )
        ]
    )

    assert "必须处理 0 封" in digest
    assert "必须关注" not in digest
    assert "为什么判断为必须处理" not in digest
    assert "All RPg students must earn" not in digest
    assert "departmental seminar" not in digest
    assert "credit" not in digest
