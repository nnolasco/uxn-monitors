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
class SlackWorkspaceData:
    name: str
    unread_dm_count: int = 0
    error: str | None = None


@dataclass
class AppSnapshot:
    outlook: OutlookData = field(default_factory=OutlookData)
    slack_workspaces: list[SlackWorkspaceData] = field(default_factory=list)


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


def _get_slack_tokens() -> list[tuple[str, str]]:
    """Find all Slack tokens from environment.

    Supports:
      SLACK_TOKEN_MYWORKSPACE=xoxp-...   → name="MyWorkspace"
      SLACK_BOT_TOKEN=xoxp-...           → name from auth_test (legacy/fallback)
    """
    tokens = []

    # Named tokens: SLACK_TOKEN_<NAME>
    for key, val in os.environ.items():
        if key.startswith("SLACK_TOKEN_") and val:
            name = key[len("SLACK_TOKEN_"):].replace("_", " ").title()
            tokens.append((name, val))

    # Legacy fallback
    if not tokens:
        legacy = os.environ.get("SLACK_BOT_TOKEN")
        if legacy:
            tokens.append(("", legacy))  # empty name = resolve from API

    return tokens


def _collect_one_slack(name: str, token: str) -> SlackWorkspaceData:
    """Collect unread DM count for one Slack workspace."""
    try:
        from slack_sdk import WebClient
        client = WebClient(token=token)

        # Resolve workspace name if not provided
        display_name = name
        if not display_name:
            try:
                auth = client.auth_test()
                display_name = auth.get("team", "Slack")
            except Exception:
                display_name = "Slack"

        # Collect DM channels (1:1 and group DMs)
        all_channels = []
        for dm_type in ["im", "mpim"]:
            try:
                response = client.conversations_list(types=dm_type, exclude_archived=True)
                all_channels.extend(response.get("channels", []))
            except Exception:
                pass

        # conversations.info per channel gives accurate unread counts
        unread = 0
        for ch in all_channels:
            try:
                info = client.conversations_info(channel=ch["id"])["channel"]
                unread += info.get("unread_count_display", 0)
            except Exception:
                continue

        return SlackWorkspaceData(name=display_name, unread_dm_count=unread)
    except Exception as e:
        return SlackWorkspaceData(name=name or "Slack", error=str(e))


def collect_slack() -> list[SlackWorkspaceData]:
    """Collect Slack data for all configured workspaces."""
    tokens = _get_slack_tokens()
    if not tokens:
        return [SlackWorkspaceData(name="Slack", error="No Slack tokens configured")]

    return [_collect_one_slack(name, token) for name, token in tokens]


def collect_apps() -> AppSnapshot:
    """Collect all app data. Called from background thread."""
    return AppSnapshot(
        outlook=collect_outlook(),
        slack_workspaces=collect_slack(),
    )
