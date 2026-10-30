---
name: coffee-check
description: Hourly productivity check. Counts GitHub PRs created/reviewed/merged, Microsoft 365 sent emails and Akiflow tasks completed in the last hour, compares to a rolling mean, and asks about coffee if more than 30% below it. Meant to run headless from a scheduler via run.sh.
disable-model-invocation: true
---

Scripts live in `~/.claude/skills/coffee-check/`. Run them with the exact command forms
below (they match the allowed-tools rules in run.sh). Do not use any other tools.

1. Get the window:
   `python3 ~/.claude/skills/coffee-check/coffee_check.py window`
   It prints `start`, `end` (UTC) and their local-time equivalents.

2. Count sent emails in the window with `mcp__claude_ai_Microsoft_365__outlook_email_search`:
   `folderName: "Sent Items"`, `afterDateTime: <start>`, `beforeDateTime: <end>`, `limit: 25`,
   `offset: 0`. No `query`, no `order`. Page with `nextOffset`/`nextCursor` until done.
   Count only messages whose sent/received time is inside the window.
   If the search errors or the tool is unavailable, print "coffee-check: M365 failed: <reason>"
   and stop. Do not record a sample.

3. Count Akiflow tasks completed in the window with `mcp__claude_ai_Akiflow__get_schedule`:
   `start_date: <end_local date minus 7 days>`, `end_date: <end_local date>` (YYYY-MM-DD),
   `completed_mode: "only_completed"`. The range filters by scheduled date, not completion
   date, so the 7-day lookback catches tasks finished late. Count tasks whose `done_at`
   (naive local time) is at or after `start_local` and before `end_local`, and whose
   `project_name` is not "Personal". If the tool is unavailable (not connected), use 0
   and continue. If it errors, print "coffee-check: Akiflow failed: <reason>" and stop
   without recording.

4. Record and score:
   `python3 ~/.claude/skills/coffee-check/coffee_check.py record --start <start> --end <end> --emails <count> --tasks <count>`
   If it prints `"ok": false`, print the error and stop.

5. If the result has `"ask": true`, run with its `message` text verbatim:
   `~/.claude/skills/coffee-check/notify.sh "Coffee check" "<message>"`

6. End with one line: `coffee-check: score=<score> mean=<mean> verdict=<verdict> tasks=<tasks_done>`, plus
   ` garmin=<hr_avg>bpm/stress <stress_avg>/bb <body_battery>` when `garmin` has readings, or
   ` garmin_error=<error>` when it has an error. A Garmin error never stops the run.

Read-only except for the state file. Never send email, post, or change anything in GitHub or M365.
