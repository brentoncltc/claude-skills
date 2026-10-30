#!/usr/bin/env python3
"""Garmin Connect readings for coffee-check. Optional; runs in the skill's .venv.

  garmin.py login
      One-time interactive login (email, password, MFA). Saves refreshable
      tokens to $GARMINTOKENS or ~/.garminconnect. Your password is not stored.
  garmin.py window --start ISO --end ISO
      Print heart rate, stress and Body Battery for the window as JSON.

Uses the unofficial garminconnect library. Data is only as fresh as your
watch's last sync.
"""
import argparse
import getpass
import json
import os
import sys
from datetime import datetime, timedelta

from garminconnect import Garmin

TOKENS = os.environ.get("GARMINTOKENS", "~/.garminconnect")
BB_MAX_AGE = timedelta(hours=3)  # ignore Body Battery readings older than this


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def ms(dt):
    return int(dt.timestamp() * 1000)


def cmd_login():
    email = input("Garmin email: ").strip()
    password = getpass.getpass("Garmin password: ")
    api = Garmin(email, password, prompt_mfa=lambda: input("MFA code: ").strip())
    api.login(TOKENS)
    print(f"Logged in as {api.get_full_name()}. Tokens saved to {TOKENS}.")


def readings(rows, lo, hi):
    """(timestamp_ms, value) pairs in [lo, hi). Value = first int after the timestamp."""
    out = []
    for row in rows or []:
        if not row or not lo <= row[0] < hi:
            continue
        val = next((v for v in row[1:] if isinstance(v, int) and not isinstance(v, bool)), None)
        if val is not None and val >= 0:  # Garmin uses negatives for "no data"
            out.append((row[0], val))
    return out


def cmd_window(args):
    api = Garmin()
    api.login(TOKENS)
    start, end = parse(args.start), parse(args.end)
    day = end.astimezone().date().isoformat()
    lo, hi = ms(start), ms(end)

    hr_day = api.get_heart_rates(day) or {}
    hr = [v for _, v in readings(hr_day.get("heartRateValues"), lo, hi)]

    stress_day = api.get_stress_data(day) or {}
    stress = [v for _, v in readings(stress_day.get("stressValuesArray"), lo, hi)]

    bb_rows = stress_day.get("bodyBatteryValuesArray")
    if not bb_rows:
        bb_days = api.get_body_battery(day) or [{}]
        bb_rows = bb_days[0].get("bodyBatteryValuesArray")
    bb = readings(bb_rows, ms(end - BB_MAX_AGE), hi)

    synced = [t for t, _ in readings(hr_day.get("heartRateValues"), 0, hi)]
    print(json.dumps({
        "ok": True,
        "hr_readings": len(hr),
        "hr_avg": round(sum(hr) / len(hr)) if hr else None,
        "hr_max": max(hr) if hr else None,
        "rhr": hr_day.get("restingHeartRate"),
        "stress_readings": len(stress),
        "stress_avg": round(sum(stress) / len(stress)) if stress else None,
        "body_battery": bb[-1][1] if bb else None,
        "last_reading_min_ago": round((hi - max(synced)) / 60000) if synced else None,
    }))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login")
    win = sub.add_parser("window")
    win.add_argument("--start", required=True)
    win.add_argument("--end", required=True)
    args = ap.parse_args()
    try:
        cmd_login() if args.cmd == "login" else cmd_window(args)
    except Exception as e:  # report, never crash the hourly check
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        sys.exit(2)


if __name__ == "__main__":
    main()
