#!/usr/bin/env python3
"""
Fetch meeting hours from Google Calendar for all SLASHR consultants.

Uses a service account with domain-wide delegation to impersonate each user.
Classifies meetings as internal (@slashr.fr only) or external.

Setup required:
  1. pip install google-auth google-api-python-client
  2. Place service account key as google_sa_key.json in this directory
  3. Configure domain-wide delegation in Google Admin Console (see README)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuration
SA_KEY_FILE = Path(__file__).parent / "google_sa_key.json"
OUTPUT_FILE = Path(__file__).parent / "calendar_meetings.json"
DOMAIN = "slashr.fr"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Consultants: ClickUp username -> Google email
CONSULTANTS = {
    "Lucas Colin": "lucas@slashr.fr",
    "Tom Chemin": "tom@slashr.fr",
    "Pierre-Antoine Henneau": "pierre-antoine@slashr.fr",
    "Maxime Legru": "maxime@slashr.fr",
    "Anthony": "anthony@slashr.fr",
    "Benoit Demonchaux": "benoit@slashr.fr",
    "Quentin Clément": "quentin@slashr.fr",
}


def get_calendar_service(sa_key_path, user_email):
    """Create a Calendar API service impersonating a user."""
    credentials = service_account.Credentials.from_service_account_file(
        str(sa_key_path), scopes=SCOPES
    )
    delegated = credentials.with_subject(user_email)
    return build("calendar", "v3", credentials=delegated)


def classify_meeting(event):
    """Classify a meeting as internal or external based on attendees.

    Internal: all attendees have @slashr.fr
    External: at least one attendee outside @slashr.fr
    """
    attendees = event.get("attendees", [])
    if not attendees:
        return None  # No attendees = not a meeting

    # Filter out resource rooms and the organizer's implicit self
    real_attendees = [
        a for a in attendees
        if not a.get("resource", False)
    ]

    if len(real_attendees) < 2:
        return None  # Solo event, not a meeting

    for a in real_attendees:
        email = a.get("email", "")
        if not email.endswith(f"@{DOMAIN}"):
            return "external"
    return "internal"


def event_duration_hours(event):
    """Calculate event duration in hours."""
    start = event.get("start", {})
    end = event.get("end", {})

    # All-day events: skip (not meetings)
    if "date" in start and "dateTime" not in start:
        return 0

    start_dt = datetime.fromisoformat(start["dateTime"])
    end_dt = datetime.fromisoformat(end["dateTime"])
    delta = (end_dt - start_dt).total_seconds() / 3600
    return round(delta, 2)


def fetch_meetings(service, time_min, time_max):
    """Fetch all events from primary calendar in the given time range."""
    events = []
    page_token = None

    while True:
        result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=2500,
            pageToken=page_token,
        ).execute()

        events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return events


def main():
    if not SA_KEY_FILE.exists():
        print(f"ERROR: Service account key not found at {SA_KEY_FILE}")
        print("See setup instructions in this file's docstring.")
        return

    # Fetch from Jan 2024 to now + 3 months
    time_min = "2024-01-01T00:00:00Z"
    time_max = (datetime.utcnow() + timedelta(days=90)).strftime("%Y-%m-%dT00:00:00Z")

    all_meetings = []
    stats = {}

    for username, email in sorted(CONSULTANTS.items()):
        print(f"\n  {username} ({email})...")
        try:
            service = get_calendar_service(SA_KEY_FILE, email)
            events = fetch_meetings(service, time_min, time_max)
        except Exception as e:
            print(f"    ERROR: {e}")
            continue

        user_internal = 0
        user_external = 0
        user_hours = 0

        for event in events:
            # Skip cancelled events
            if event.get("status") == "cancelled":
                continue

            # Skip events where user declined
            attendees = event.get("attendees", [])
            user_response = None
            for a in attendees:
                if a.get("self", False) or a.get("email", "") == email:
                    user_response = a.get("responseStatus")
                    break
            if user_response == "declined":
                continue

            meeting_type = classify_meeting(event)
            if meeting_type is None:
                continue

            duration = event_duration_hours(event)
            if duration <= 0 or duration > 12:  # Skip absurd durations
                continue

            start = event.get("start", {}).get("dateTime", "")
            if not start:
                continue

            start_dt = datetime.fromisoformat(start)
            month = start_dt.strftime("%Y-%m")
            date = start_dt.strftime("%Y-%m-%d")

            all_meetings.append({
                "user": username,
                "email": email,
                "date": date,
                "month": month,
                "hours": duration,
                "type": meeting_type,
                "summary": event.get("summary", "(sans titre)"),
                "attendee_count": len([
                    a for a in attendees
                    if not a.get("resource", False)
                ]),
            })

            user_hours += duration
            if meeting_type == "internal":
                user_internal += 1
            else:
                user_external += 1

        stats[username] = {
            "total_events": user_internal + user_external,
            "internal": user_internal,
            "external": user_external,
            "total_hours": round(user_hours, 1),
        }
        print(f"    {user_internal + user_external} réunions ({user_hours:.1f}h) — "
              f"{user_internal} internes, {user_external} externes")

    # Sort by date
    all_meetings.sort(key=lambda m: (m["date"], m["user"]))

    output = {
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "time_range": {"min": time_min, "max": time_max},
        "stats": stats,
        "meetings": all_meetings,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n  Saved {len(all_meetings)} meetings to {OUTPUT_FILE}")
    total_h = sum(s["total_hours"] for s in stats.values())
    print(f"  Total: {total_h:.0f}h de réunions")


if __name__ == "__main__":
    main()
