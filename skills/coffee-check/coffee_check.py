#!/usr/bin/env python3
"""Hourly productivity check: GitHub PR activity + sent emails vs a rolling mean.

  coffee_check.py window
      Print the 60-minute window ending now (UTC and local time).
  coffee_check.py record --start ISO --end ISO --emails N
      Count GitHub PR activity in the window, add the sent-email count,
      compare to the rolling mean, record the sample, print a JSON verdict.

Uses the system's local timezone. Set COFFEE_CHECK_GH_LOGIN to skip the
`gh api user` lookup, and COFFEE_CHECK_STATE to move the state file.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

STATE = os.path.expanduser(
    os.environ.get("COFFEE_CHECK_STATE", "~/.claude/productivity/coffee-check.json"))
MAX_SAMPLES = 200
MIN_SAMPLES = 1
THRESHOLD = 0.7          # unproductive when score < 70% of mean
ASK_HOURS = range(7, 15)  # 7:00 AM through the 2:00 PM run, local time


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def fail(msg):
    print(json.dumps({"ok": False, "error": msg}))
    sys.exit(2)


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        fail(f"gh {args[0]} failed: {r.stderr.strip()}")
    return r.stdout


def cmd_window():
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = end - timedelta(hours=1)
    print(json.dumps({
        "start": start.isoformat().replace("+00:00", "Z"),
        "end": end.isoformat().replace("+00:00", "Z"),
        "start_local": start.astimezone().isoformat(),
        "end_local": end.astimezone().isoformat(),
    }))


def github_counts(start, end):
    login = os.environ.get("COFFEE_CHECK_GH_LOGIN") or json.loads(gh("api", "user"))["login"]
    events = []
    for page in (1, 2, 3):  # the events API serves at most 300 events
        batch = json.loads(gh("api", f"users/{login}/events?per_page=100&page={page}"))
        events += batch
        if not batch or parse(batch[-1]["created_at"]) < start:
            break

    created, merged, reviewed = 0, 0, set()
    for e in events:
        if not start <= parse(e["created_at"]) < end:
            continue
        p = e.get("payload", {})
        action = p.get("action")
        if e["type"] == "PullRequestEvent":
            if action == "opened":
                created += 1
            elif action == "merged" or (
                    action == "closed" and (p.get("pull_request") or {}).get("merged")):
                merged += 1
        elif e["type"] == "PullRequestReviewEvent":
            num = p.get("number") or (p.get("pull_request") or {}).get("number")
            reviewed.add((e["repo"]["name"], num))
    return {"prs_created": created, "prs_reviewed": len(reviewed), "prs_merged": merged}


def load_state():
    if not os.path.exists(STATE):
        return {"samples": [], "updated": None}
    with open(STATE) as f:
        return json.load(f)


def save_state(state):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE)


def cmd_record(args):
    start, end = parse(args.start), parse(args.end)
    counts = github_counts(start, end)
    score = sum(counts.values()) + args.emails

    end_local = end.astimezone()
    in_window = end_local.weekday() < 5 and end_local.hour in ASK_HOURS

    state = load_state()
    samples = state["samples"]
    # A rerun for the same hour replaces that hour's sample instead of adding one.
    if samples and abs(parse(samples[-1]["ts"]) - end) < timedelta(minutes=30):
        samples.pop()
    prior = samples[-MAX_SAMPLES:]
    mean = sum(s["score"] for s in prior) / len(prior) if prior else 0.0

    if not in_window:
        verdict, ask = "outside_window_not_recorded", False
    else:
        samples.append({"ts": args.end, "score": score, "gh": counts, "emails_sent": args.emails})
        state["samples"] = samples[-MAX_SAMPLES:]
        state["updated"] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        if len(prior) < MIN_SAMPLES:
            verdict, ask = "building_baseline", False
        elif mean == 0:
            verdict, ask = "mean_zero", False
        elif score < THRESHOLD * mean:
            verdict, ask = "unproductive", True
        else:
            verdict, ask = "productive", False

    print(json.dumps({
        "ok": True, "score": score, "mean": round(mean, 2),
        "threshold": round(THRESHOLD * mean, 2), "prior_samples": len(prior),
        "gh": counts, "emails_sent": args.emails, "verdict": verdict, "ask": ask,
    }))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("window")
    rec = sub.add_parser("record")
    rec.add_argument("--start", required=True)
    rec.add_argument("--end", required=True)
    rec.add_argument("--emails", type=int, required=True)
    args = ap.parse_args()
    cmd_window() if args.cmd == "window" else cmd_record(args)


if __name__ == "__main__":
    main()
