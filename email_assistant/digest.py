from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
import re

from email_assistant.models import EmailAnalysis, EmailCategory
from email_assistant.sender_filter import clean_forwarded_subject


CATEGORY_TITLES = {
    EmailCategory.MUST_ACTION: "Must Do",
    EmailCategory.MUST_ATTEND: "Must Attend",
    EmailCategory.ACADEMIC_NOTICE: "Academic Notices",
    EmailCategory.OPTIONAL_EVENT: "Optional Events",
    EmailCategory.GENERAL: "General",
}

CATEGORY_ORDER = [
    EmailCategory.MUST_ACTION,
    EmailCategory.MUST_ATTEND,
    EmailCategory.OPTIONAL_EVENT,
    EmailCategory.ACADEMIC_NOTICE,
    EmailCategory.GENERAL,
]

ZH_CATEGORY_TITLES = {
    EmailCategory.MUST_ACTION: "必须处理",
    EmailCategory.MUST_ATTEND: "必须参加",
    EmailCategory.OPTIONAL_EVENT: "可以考虑参加 / 可做",
    EmailCategory.ACADEMIC_NOTICE: "需要留意的学术 notice",
    EmailCategory.GENERAL: "普通通知",
}

def build_daily_digest(analyses: list[EmailAnalysis]) -> str:
    grouped: dict[EmailCategory, list[EmailAnalysis]] = defaultdict(list)
    for analysis in analyses:
        grouped[analysis.category].append(analysis)

    lines = ["PolyU Daily Email Digest", ""]
    for category in CATEGORY_ORDER:
        items = grouped.get(category, [])
        if not items:
            continue
        lines.append(f"{CATEGORY_TITLES[category]} ({len(items)})")
        for item in items:
            lines.extend(_format_item(item))
        lines.append("")

    if len(lines) == 2:
        lines.append("No processed emails found for this period.")

    return "\n".join(lines).rstrip()


def build_daily_digest_zh(
    analyses: list[EmailAnalysis],
    *,
    digest_date: date | None = None,
) -> str:
    return build_human_daily_digest_zh(analyses, digest_date=digest_date)


def build_human_daily_digest_zh(
    analyses: list[EmailAnalysis],
    *,
    digest_date: date | None = None,
    period_label: str = "过去 24 小时",
) -> str:
    digest_date = digest_date or date.today()
    grouped: dict[EmailCategory, list[EmailAnalysis]] = defaultdict(list)
    for analysis in analyses:
        grouped[analysis.category].append(analysis)

    total = len(analyses)
    action_count = len(grouped.get(EmailCategory.MUST_ACTION, []))
    attend_count = len(grouped.get(EmailCategory.MUST_ATTEND, []))
    optional_count = len(grouped.get(EmailCategory.OPTIONAL_EVENT, []))

    prepared = [_prepare_item(item) for item in analyses]
    today_items = _today_activities(prepared, digest_date)
    upcoming_items = _upcoming_items(prepared, digest_date, today_items)
    other_items = _other_items(prepared, today_items, upcoming_items)

    lines = [
        f"PolyU 每日 Email Digest · {digest_date.isoformat()}",
        "",
        f"{period_label}共分析 {total} 封邮件。",
        f"必须处理 {action_count} 封；必须参加 {attend_count} 封；可以考虑参加 / 可做 {optional_count} 封。",
        "",
    ]

    must_items = [
        item
        for item in prepared
        if item.analysis.category in {EmailCategory.MUST_ACTION, EmailCategory.MUST_ATTEND}
    ]
    if must_items:
        lines.append("必须关注")
        for item in sorted(must_items, key=_sort_key):
            lines.extend(
                _format_human_item(
                    item,
                    digest_date=digest_date,
                    include_mandatory_evidence=True,
                )
            )
        lines.append("")
    else:
        lines.extend(["目前没有必须完成或必须参加的事项。", ""])

    if today_items:
        lines.append("今天的活动")
        for item in sorted(today_items, key=_sort_key):
            lines.extend(_format_human_item(item, digest_date=digest_date))
        lines.append("")

    if upcoming_items:
        lines.append("接下来值得关注")
        for item in sorted(upcoming_items, key=_sort_key):
            lines.extend(_format_human_item(item, digest_date=digest_date))
        lines.append("")

    if other_items:
        lines.append("其他通知")
        for item in sorted(other_items, key=_sort_key):
            lines.extend(_format_human_item(item, digest_date=digest_date))
        lines.append("")

    return "\n".join(lines).rstrip()


def build_structured_daily_digest_zh(analyses: list[EmailAnalysis]) -> str:
    grouped: dict[EmailCategory, list[EmailAnalysis]] = defaultdict(list)
    for analysis in analyses:
        grouped[analysis.category].append(analysis)

    total = len(analyses)
    action_count = len(grouped.get(EmailCategory.MUST_ACTION, []))
    attend_count = len(grouped.get(EmailCategory.MUST_ATTEND, []))
    optional_count = len(grouped.get(EmailCategory.OPTIONAL_EVENT, []))

    lines = [
        "PolyU 每日 email digest",
        "",
        f"今日共分析 {total} 封 PolyU email。",
        f"必须处理 {action_count} 封；必须参加 {attend_count} 封；可以考虑参加 / 可做 {optional_count} 封。",
        "",
    ]
    for category in CATEGORY_ORDER:
        items = grouped.get(category, [])
        if not items:
            continue
        lines.append(f"{ZH_CATEGORY_TITLES[category]} ({len(items)})")
        for item in items:
            lines.extend(_format_item_zh(item))
        lines.append("")

    return "\n".join(lines).rstrip()


def _format_item(item: EmailAnalysis) -> list[str]:
    lines = [f"- {item.summary or item.email_id}"]
    details = []
    if item.action:
        details.append(f"Action: {item.action}")
    if item.deadline:
        details.append(f"Deadline: {item.deadline}")
    if item.event_time:
        details.append(f"Time: {item.event_time}")
    if item.location:
        details.append(f"Location: {item.location}")
    if details:
        lines.append(f"  {' | '.join(details)}")
    return lines


def _format_item_zh(item: EmailAnalysis) -> list[str]:
    title = clean_forwarded_subject(item.subject or item.email_id)
    lines = [f"- 邮件标题：{title}", f"  Summary：{item.summary or '没有摘要'}"]
    details = []
    if item.action:
        details.append(f"Action：{item.action}")
    if item.deadline:
        details.append(f"Deadline：{item.deadline}")
    if item.event_time:
        details.append(f"Event time：{item.event_time}")
    if item.location:
        details.append(f"Venue：{item.location}")
    if item.evidence:
        details.append(f"判断依据：{item.evidence}")
    if details:
        lines.append(f"  {'；'.join(details)}")
    return lines


@dataclass(frozen=True)
class DigestItem:
    analysis: EmailAnalysis
    title: str
    event_start: datetime | None
    event_end: datetime | None
    deadline: datetime | None


def _prepare_item(analysis: EmailAnalysis) -> DigestItem:
    return DigestItem(
        analysis=analysis,
        title=_human_title(analysis),
        event_start=_parse_first_datetime(analysis.event_time),
        event_end=_parse_range_end(analysis.event_time),
        deadline=_parse_first_datetime(analysis.deadline),
    )


def _today_activities(items: list[DigestItem], digest_date: date) -> set[DigestItem]:
    return {
        item
        for item in items
        if item.event_start and item.event_start.date() == digest_date
    }


def _upcoming_items(
    items: list[DigestItem],
    digest_date: date,
    today_items: set[DigestItem],
) -> set[DigestItem]:
    upcoming = set()
    for item in items:
        if item in today_items:
            continue
        if item.deadline and item.deadline.date() >= digest_date:
            upcoming.add(item)
            continue
        if item.event_start and item.event_start.date() > digest_date:
            upcoming.add(item)
    return upcoming


def _other_items(
    items: list[DigestItem],
    today_items: set[DigestItem],
    upcoming_items: set[DigestItem],
) -> list[DigestItem]:
    excluded = today_items | upcoming_items
    return [
        item
        for item in items
        if item not in excluded
        and item.analysis.category not in {EmailCategory.MUST_ACTION, EmailCategory.MUST_ATTEND}
    ]


def _format_human_item(
    item: DigestItem,
    *,
    digest_date: date,
    include_mandatory_evidence: bool = False,
) -> list[str]:
    analysis = item.analysis
    prefix = _time_prefix(item, digest_date)
    lines = [f"{prefix}｜{item.title}" if prefix else item.title]
    source_title = clean_forwarded_subject(analysis.subject or "")
    if source_title and source_title != item.title:
        lines.append(f"来源邮件：{source_title}")

    if analysis.location:
        lines.append(f"📍 {analysis.location}")

    description = _human_description(analysis)
    if description:
        lines.append(description)

    extra = _extra_line(item)
    if extra:
        lines.append(extra)

    if include_mandatory_evidence and analysis.evidence:
        label = "为什么判断为必须参加" if analysis.category == EmailCategory.MUST_ATTEND else "为什么判断为必须处理"
        lines.append(f"{label}：{analysis.evidence}")

    lines.append("")
    return lines


def _human_title(analysis: EmailAnalysis) -> str:
    subject = clean_forwarded_subject(analysis.subject or "")
    text = " ".join(filter(None, [subject, analysis.summary, analysis.action]))
    lower = text.lower()

    if "orientation showcase" in lower:
        return "PolyU Student Orientation Showcase"
    if "polyu cinema" in lower or "find your voice" in lower or "熱血合唱團" in text:
        return "PolyU Cinema《熱血合唱團 / Find Your Voice》"
    if "aae research seminar" in lower:
        return "AAE Research Seminar"
    if "cspse research seminar" in lower:
        return "CSPSE Research Seminar"
    if "global university presidents" in lower:
        return "Global University Presidents & Leaders Summit"

    return subject or analysis.summary or analysis.email_id


def _human_description(analysis: EmailAnalysis) -> str:
    summary = (analysis.summary or "").strip()
    if not summary:
        return ""
    return summary.rstrip("。.") + "。"


def _extra_line(item: DigestItem) -> str | None:
    analysis = item.analysis
    parts = []
    if item.deadline:
        parts.append(f"有明确 deadline：{_format_date(item.deadline)}")
    if analysis.action and analysis.category != EmailCategory.GENERAL:
        action = analysis.action.rstrip("。.")
        parts.append(action)
    if not parts:
        return None
    return "；".join(parts) + "。"


def _time_prefix(item: DigestItem, digest_date: date) -> str | None:
    if item.deadline and (
        not item.event_start or item.deadline.date() <= item.event_start.date()
    ):
        return f"{_format_date(item.deadline)}前"
    if item.event_start:
        return _format_datetime_range(item.event_start, item.event_end, digest_date)
    return None


def _sort_key(item: DigestItem) -> tuple[int, datetime]:
    analysis = item.analysis
    if analysis.category == EmailCategory.MUST_ACTION:
        priority = 0
    elif analysis.category == EmailCategory.MUST_ATTEND:
        priority = 1
    elif item.deadline:
        priority = 2
    elif item.event_start:
        priority = 3
    elif analysis.category == EmailCategory.ACADEMIC_NOTICE:
        priority = 4
    else:
        priority = 5

    when = item.deadline or item.event_start or datetime.max
    return priority, when


def _format_datetime_range(start: datetime, end: datetime | None, digest_date: date) -> str:
    date_prefix = "" if start.date() == digest_date else f"{_format_date(start)} "
    if end and end.date() == start.date():
        return f"{date_prefix}{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"
    return f"{date_prefix}{start.strftime('%H:%M')}"


def _format_date(value: datetime) -> str:
    return f"{value.month} 月 {value.day} 日"


def _parse_first_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    iso = _parse_iso_like(text)
    if iso:
        return iso

    match = re.search(r"(?P<date>\d{4}-\d{2}-\d{2})(?:[ T](?P<time>\d{1,2}:\d{2}))?", text)
    if not match:
        return None
    time_text = match.group("time") or "00:00"
    return datetime.fromisoformat(f"{match.group('date')}T{time_text}")


def _parse_range_end(value: str | None) -> datetime | None:
    if not value:
        return None
    start = _parse_first_datetime(value)
    if not start:
        return None

    times = re.findall(r"\b(\d{1,2}:\d{2})\b", value)
    if len(times) < 2:
        return None

    hour, minute = [int(part) for part in times[1].split(":", 1)]
    return datetime.combine(start.date(), time(hour, minute))


def _parse_iso_like(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)
