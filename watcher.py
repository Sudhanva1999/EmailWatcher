#!/usr/bin/env python3
"""
Email watcher — polls your mailbox and fires Telegram alerts for matching emails.
Designed to run as a cron job every 2 hours.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dotenv import load_dotenv
load_dotenv(HERE / ".env")

from email_providers import get_email_provider
from email_providers.base import EmailMessage
from notifier import NotificationPayload, TelegramNotifier

STATE_FILE = HERE / "state.json"
CONFIG_FILE = HERE / "config.json"
MAX_NOTIFIED_IDS = 2000  # cap stored IDs to avoid unbounded growth


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"last_checked": None, "notified_ids": []}


def save_state(state: dict) -> None:
    # Keep only the last MAX_NOTIFIED_IDS to prevent file bloat
    if len(state.get("notified_ids", [])) > MAX_NOTIFIED_IDS:
        state["notified_ids"] = state["notified_ids"][-MAX_NOTIFIED_IDS:]
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print(f"ERROR: {CONFIG_FILE} not found.")
        print("Copy config.example.json to config.json and edit it to define your criteria.")
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def matches_criterion(email: EmailMessage, criterion: dict) -> bool:
    keywords = [k.lower() for k in criterion.get("keywords", [])]
    if not keywords:
        return False

    fields = criterion.get("fields", ["subject", "body"])
    match_any = criterion.get("match_any", True)

    parts: list[str] = []
    if "subject" in fields:
        parts.append(email.subject.lower())
    if "body" in fields:
        parts.append(email.body.lower())
    if "snippet" in fields:
        parts.append(email.snippet.lower())
    if "sender" in fields:
        parts.append(email.sender.lower())

    combined = " ".join(parts)

    if match_any:
        return any(kw in combined for kw in keywords)
    return all(kw in combined for kw in keywords)


def build_alert_text(email: EmailMessage) -> str:
    date_str = email.date.strftime("%Y-%m-%d %H:%M UTC")
    preview = (email.snippet or email.body)[:300].strip()
    return (
        f"From: {email.sender}\n"
        f"Date: {date_str}\n"
        f"Subject: {email.subject}\n\n"
        f"{preview}"
    )


def main() -> None:
    config = load_config()
    criteria = config.get("criteria", [])
    if not criteria:
        print("No criteria defined in config.json — nothing to watch.")
        return

    state = load_state()
    notified_ids: set[str] = set(state.get("notified_ids", []))
    lookback_hours = int(os.getenv("LOOKBACK_HOURS", "2"))

    last_checked_str = state.get("last_checked")
    if last_checked_str:
        since = datetime.fromisoformat(last_checked_str)
    else:
        since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    now = datetime.now(timezone.utc)

    try:
        notifier = TelegramNotifier()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    provider = get_email_provider()
    try:
        provider.authenticate()
    except Exception as e:
        print(f"ERROR: Authentication failed: {e}")
        sys.exit(1)

    print(f"[{now.strftime('%Y-%m-%d %H:%M UTC')}] Watching {provider.account!r} since {since.isoformat()}")

    checked = 0
    alerts_sent = 0
    new_notified: list[str] = []

    for email in provider.fetch_emails(since=since, order="asc"):
        checked += 1
        if email.id in notified_ids:
            continue

        for criterion in criteria:
            if matches_criterion(email, criterion):
                rule_name = criterion.get("name", "Match")
                print(f"  MATCH [{rule_name}]: {email.subject!r} from {email.sender}")
                payload = NotificationPayload(
                    title=f"📧 Email Alert: {rule_name}",
                    body=build_alert_text(email),
                )
                try:
                    notifier.send(payload)
                    alerts_sent += 1
                except Exception as e:
                    print(f"  WARNING: Failed to send Telegram alert: {e}")
                new_notified.append(email.id)
                break  # one alert per email even if multiple criteria match

    print(f"Done. Checked {checked} emails, sent {alerts_sent} alerts.")

    state["last_checked"] = now.isoformat()
    state["notified_ids"] = list(notified_ids) + new_notified
    save_state(state)


if __name__ == "__main__":
    main()
