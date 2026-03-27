import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class AppointmentInfo:
    subject: str
    start_time: str  # formatted "10:30 AM"


@dataclass
class OutlookData:
    unread_count: int = 0
    appointments: list[AppointmentInfo] = field(default_factory=list)
    error: str | None = None


@dataclass
class SlackData:
    unread_dm_count: int = 0
    error: str | None = None


@dataclass
class AppSnapshot:
    outlook: OutlookData = field(default_factory=OutlookData)
    slack: SlackData = field(default_factory=SlackData)


def collect_outlook() -> OutlookData:
    """Collect Outlook unread count and upcoming appointments via COM."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
            ns = outlook.GetNamespace("MAPI")

            # Unread emails
            inbox = ns.GetDefaultFolder(6)  # olFolderInbox
            unread_items = inbox.Items.Restrict("[Unread] = true")
            unread_count = unread_items.Count

            # Today's appointments
            calendar = ns.GetDefaultFolder(9)  # olFolderCalendar
            now = datetime.now()
            end_of_day = now.replace(hour=23, minute=59, second=59)
            start_str = now.strftime("%m/%d/%Y %H:%M %p")
            end_str = end_of_day.strftime("%m/%d/%Y %H:%M %p")

            appts = calendar.Items
            appts.Sort("[Start]")
            appts.IncludeRecurrences = True
            restriction = f"[Start] >= '{start_str}' AND [Start] <= '{end_str}'"
            filtered = appts.Restrict(restriction)

            appointments = []
            for i in range(min(filtered.Count, 3)):
                item = filtered.Item(i + 1)  # COM is 1-indexed
                try:
                    start = item.Start
                    subject = item.Subject or "No subject"
                    time_str = start.strftime("%I:%M %p") if hasattr(start, 'strftime') else str(start)
                    appointments.append(AppointmentInfo(
                        subject=subject[:30],
                        start_time=time_str,
                    ))
                except Exception:
                    continue

            return OutlookData(
                unread_count=unread_count,
                appointments=appointments,
            )
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        return OutlookData(error=str(e))


def collect_slack() -> SlackData:
    """Collect Slack unread DM count via SDK."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        return SlackData(error="SLACK_BOT_TOKEN not set")

    try:
        from slack_sdk import WebClient
        client = WebClient(token=token)
        response = client.conversations_list(types="im", exclude_archived=True)
        channels = response.get("channels", [])
        unread = sum(ch.get("unread_count_display", 0) for ch in channels)
        return SlackData(unread_dm_count=unread)
    except Exception as e:
        return SlackData(error=str(e))


def collect_apps() -> AppSnapshot:
    """Collect all app data. Called from background thread."""
    return AppSnapshot(
        outlook=collect_outlook(),
        slack=collect_slack(),
    )
