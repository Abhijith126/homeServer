#!/usr/bin/env python3
"""Render a validated systemd timer; no host changes when called directly."""
import argparse
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEDULES = ("5min", "hourly", "daily", "weekly", "monthly")


def timer(schedule, time="03:00", timezone="Europe/Amsterdam"):
    if schedule not in SCHEDULES:
        raise ValueError("Schedule must be one of: " + ", ".join(SCHEDULES))
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time):
        raise ValueError("Time must be HH:MM (24-hour clock)")
    if not re.fullmatch(r"[A-Za-z0-9_+/-]+", timezone):
        raise ValueError("Use an IANA timezone, e.g. Europe/Amsterdam")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("Unknown timezone: " + timezone) from error
    if schedule == "5min":
        timing = "OnActiveSec=2min\nOnUnitInactiveSec=5min"
    else:
        calendar = {
            "hourly": "*-*-* *:00:00",
            "daily": f"*-*-* {time}:00",
            "weekly": f"Mon *-*-* {time}:00",
            "monthly": f"*-*-01 {time}:00",
        }[schedule]
        timing = f"OnCalendar={calendar} {timezone}\nPersistent=true"
    return (f"[Unit]\nDescription=Check and deploy homelab updates ({schedule})\n\n"
            f"[Timer]\n{timing}\nRandomizedDelaySec=30s\n"
            "Unit=homelab-deploy.service\n\n[Install]\nWantedBy=timers.target\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", default="weekly")
    parser.add_argument("--time", default="03:00")
    parser.add_argument("--timezone", default="Europe/Amsterdam")
    args = parser.parse_args()
    try:
        print(timer(args.schedule, args.time, args.timezone), end="")
    except ValueError as error:
        parser.error(str(error))
