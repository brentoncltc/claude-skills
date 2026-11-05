#!/usr/bin/env python3
"""Hourly productivity check: GitHub PR activity + sent emails vs a rolling mean.

  coffee_check.py window
      Print the 60-minute window ending now (UTC and local time).
  coffee_check.py record --start ISO --end ISO --emails N [--tasks N]
      Count GitHub PR activity in the window, add sent emails and tasks completed,
      compare to the rolling mean, record the sample, print a JSON verdict.
  coffee_check.py error --start ISO --end ISO --reason TEXT
      Log a run that failed before scoring (M365 or Akiflow error).
  coffee_check.py backfill
      Copy state-file samples missing from the history file into it. Safe to rerun.

Every run, in or out of the ask window and including failures, appends one line
to the history file (COFFEE_CHECK_HISTORY) for later analysis. It is never trimmed.

Uses the system's local timezone. Set COFFEE_CHECK_GH_LOGIN to skip the
`gh api user` lookup, and COFFEE_CHECK_STATE to move the state file.
If garmin.py is set up (.venv plus saved tokens), Garmin readings shape the nudge.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE = os.path.expanduser(
    os.environ.get("COFFEE_CHECK_STATE", "~/.claude/productivity/coffee-check.json"))
HISTORY = os.path.expanduser(
    os.environ.get("COFFEE_CHECK_HISTORY", "~/.claude/productivity/coffee-check-history.jsonl"))
MAX_SAMPLES = 200
MIN_SAMPLES = 1
THRESHOLD = 0.7          # unproductive when score < 70% of mean
ASK_HOURS = range(7, 17)  # 7:00 AM through the 4:00 PM run, local time
NO_CELSIUS_FROM = 12      # no Celsius suggestions from noon on (sleep)
NO_CAFFEINE_FROM = 14     # no caffeine at all from 2:00 PM on
NO_CAFFEINE = "No more caffeine, but maybe you need some metal or a kick in the @ss?"
WIRED_STRESS = 50         # Garmin stress average above this = wired
WIRED_HR_OVER_RHR = 20    # or average HR this far above resting HR
TIRED_BODY_BATTERY = 30   # Body Battery below this = tired
MIN_READINGS = 5          # fewer Garmin readings in the window = ignore them

HERE = Path(__file__).resolve().parent
GARMIN_PY = HERE / ".venv" / "bin" / "python"
GARMIN_TOKENS = Path(os.path.expanduser(os.environ.get("GARMINTOKENS", "~/.garminconnect")))


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class CheckError(Exception):
    pass


def fail(msg):
    print(json.dumps({"ok": False, "error": msg}))
    sys.exit(2)


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise CheckError(f"gh {args[0]} failed: {r.stderr.strip()}")
    return r.stdout


def append_history(entry):
    """One JSON line per run. Append-only; a history write failure never breaks the check."""
    try:
        os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
        with open(HISTORY, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        print(f"coffee-check: history write failed: {e}", file=sys.stderr)


def run_info(start, end):
    end_local = end.astimezone()
    return {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "start": start.isoformat().replace("+00:00", "Z"),
        "end": end.isoformat().replace("+00:00", "Z"),
        "end_local": end_local.isoformat(),
        "weekday": end_local.strftime("%a"),
        "hour_local": end_local.hour,
        "in_window": end_local.weekday() < 5 and end_local.hour in ASK_HOURS,
    }


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


def garmin_readings(start, end):
    """Garmin readings for the window, None if not set up, or {"error": ...}."""
    if not (GARMIN_PY.exists() and GARMIN_TOKENS.exists()):
        return None
    try:
        r = subprocess.run(
            [str(GARMIN_PY), str(HERE / "garmin.py"), "window", "--start", start, "--end", end],
            capture_output=True, text=True, timeout=90)
        data = json.loads(r.stdout)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    return data if data.get("ok") else {"error": data.get("error", "unknown")}


def nudge(score, mean, g, end_local):
    head = f"Last hour: {score} vs your average of {mean:.1f}."
    if end_local.hour >= NO_CAFFEINE_FROM:
        caffeine = NO_CAFFEINE
    elif end_local.hour >= NO_CELSIUS_FROM:
        caffeine = "Need a coffee?"
    else:
        caffeine = "Need a coffee? Or maybe a Celsius?"
    g = g if g and "error" not in g else {}
    hr_ok = (g.get("hr_readings") or 0) >= MIN_READINGS
    stress_ok = (g.get("stress_readings") or 0) >= MIN_READINGS
    hr, rhr, stress, bb = g.get("hr_avg"), g.get("rhr"), g.get("stress_avg"), g.get("body_battery")

    if (stress_ok and stress > WIRED_STRESS) or (hr_ok and rhr and hr >= rhr + WIRED_HR_OVER_RHR):
        detail = ", ".join(x for x in (
            f"heart rate {hr} bpm (resting {rhr})" if hr_ok and rhr else "",
            f"stress {stress}" if stress_ok else "") if x)
        return f"{head} {detail[0].upper()}{detail[1:]}. You're wired, not tired. Water and a walk?"
    if bb is not None and bb < TIRED_BODY_BATTERY:
        return f"{head} Body Battery's at {bb}. {caffeine}"
    return f"{head} {caffeine}"


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
    info = run_info(start, end)
    try:
        counts = github_counts(start, end)
    except CheckError as e:
        append_history({**info, "ok": False, "error": str(e),
                        "emails_sent": args.emails, "tasks_done": args.tasks})
        raise
    score = sum(counts.values()) + args.emails + args.tasks
    garmin = garmin_readings(args.start, args.end)

    end_local = end.astimezone()
    in_window = info["in_window"]

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
        samples.append({"ts": args.end, "score": score, "gh": counts,
                        "emails_sent": args.emails, "tasks_done": args.tasks, "garmin": garmin})
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

    result = {
        "ok": True, "score": score, "mean": round(mean, 2),
        "threshold": round(THRESHOLD * mean, 2), "prior_samples": len(prior),
        "gh": counts, "emails_sent": args.emails, "tasks_done": args.tasks, "garmin": garmin,
        "verdict": verdict, "ask": ask,
        "message": nudge(score, mean, garmin, end_local) if ask else None,
    }
    append_history({**info, "recorded": in_window, **result})
    print(json.dumps(result))


def cmd_error(args):
    append_history({**run_info(parse(args.start), parse(args.end)),
                    "ok": False, "error": args.reason})
    print(json.dumps({"ok": True, "logged": args.reason}))


def cmd_backfill():
    seen = set()
    if os.path.exists(HISTORY):
        with open(HISTORY) as f:
            seen = {json.loads(line).get("end") for line in f if line.strip()}
    added, prior = 0, []
    for smp in load_state()["samples"]:
        end = parse(smp["ts"])
        key = end.isoformat().replace("+00:00", "Z")
        mean = sum(p["score"] for p in prior) / len(prior) if prior else 0.0
        prior.append(smp)
        if key in seen:
            continue
        info = run_info(end - timedelta(hours=1), end)
        info["run_at"] = None
        append_history({
            **info, "recorded": True, "ok": True, "backfilled": True,
            "score": smp["score"], "mean": round(mean, 2), "threshold": round(THRESHOLD * mean, 2),
            "prior_samples": len(prior) - 1, "gh": smp.get("gh"),
            "emails_sent": smp.get("emails_sent"), "tasks_done": smp.get("tasks_done"),
            "garmin": smp.get("garmin"), "verdict": None, "ask": None, "message": None})
        added += 1
    print(json.dumps({"ok": True, "added": added}))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("window")
    rec = sub.add_parser("record")
    rec.add_argument("--start", required=True)
    rec.add_argument("--end", required=True)
    rec.add_argument("--emails", type=int, required=True)
    rec.add_argument("--tasks", type=int, default=0, help="Akiflow tasks completed")
    err = sub.add_parser("error")
    err.add_argument("--start", required=True)
    err.add_argument("--end", required=True)
    err.add_argument("--reason", required=True)
    sub.add_parser("backfill")
    args = ap.parse_args()
    try:
        {"window": lambda a: cmd_window(), "record": cmd_record, "error": cmd_error,
         "backfill": lambda a: cmd_backfill()}[args.cmd](args)
    except CheckError as e:
        fail(str(e))


if __name__ == "__main__":
    main()
